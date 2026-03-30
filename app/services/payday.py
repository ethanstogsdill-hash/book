"""Payday engine — generates settlement records for a given week."""
from app import database as db_mod


async def run_payday(db, week_ending: str) -> dict:
    """Calculate and create settlements for the given week.

    Logic:
    1. For each direct player (no sub-agent): create individual settlement
    2. For each sub-agent: sum all their players' nets, apply vig split, create one settlement
    3. Calculate backer settlement from the total
    """
    # Check if settlements already exist for this week
    existing = await db_mod.get_settlements(db, week_ending)
    if existing:
        return {"error": f"Settlements already exist for {week_ending}. Delete them first to regenerate."}

    # Get all players with their sub-agent info
    players = await db_mod.get_players(db)
    if not players:
        return {"error": "No players found. Sync data first."}

    settings = await db_mod.get_all_settings(db)
    vig_rate = float(settings.get("default_vig_rate", "10")) / 100
    backer_split = float(settings.get("backer_vig_split", "50")) / 100

    # Group players
    direct_players = [p for p in players if p["sub_agent_id"] is None]
    sub_agent_groups = {}
    for p in players:
        if p["sub_agent_id"]:
            sid = p["sub_agent_id"]
            if sid not in sub_agent_groups:
                sub_agent_groups[sid] = []
            sub_agent_groups[sid].append(p)

    settlements_created = 0
    total_net = 0

    # 1. Direct player settlements
    for p in direct_players:
        net = p["win_loss"]  # negative = player lost = house wins
        if net == 0:
            continue

        amount = abs(net)
        # Player lost (negative win_loss) → they owe us (collect)
        # Player won (positive win_loss) → we owe them (pay)
        direction = "collect" if net < 0 else "pay"

        await db_mod.create_settlement(db, {
            "week_ending": week_ending,
            "counterparty_type": "player",
            "counterparty_id": p["id"],
            "counterparty_name": p["name"] or p["account_id"],
            "amount": amount,
            "direction": direction,
            "vig_amount": 0,
            "notes": f"Direct player settlement",
        })
        settlements_created += 1
        total_net += amount if direction == "collect" else -amount

        # Create weekly result record
        await db_mod.upsert_weekly_result(db, {
            "player_id": p["id"],
            "sub_agent_id": None,
            "week_ending": week_ending,
            "won_lost": net,
            "vig": 0,
            "net": net,
        })

    # 2. Sub-agent settlements
    for sub_id, sub_players in sub_agent_groups.items():
        sub = await db_mod.get_sub_agent(db, sub_id)
        if not sub:
            continue

        # Sum all players under this sub-agent
        total_player_net = sum(p["win_loss"] for p in sub_players)
        total_player_losses = sum(abs(p["win_loss"]) for p in sub_players if p["win_loss"] < 0)

        # Vig calculation: juice earned on losing bets
        vig_earned = total_player_losses * vig_rate

        # Sub-agent keeps their percentage of the vig
        sub_vig_split = sub.get("vig_split", 0) / 100
        sub_vig_amount = vig_earned * sub_vig_split

        # Net to settle with sub-agent
        # If players net lost: we collect (total losses - sub's vig cut)
        # If players net won: we pay (total wins + we keep vig)
        if total_player_net < 0:
            # Players lost overall — house wins
            settle_amount = abs(total_player_net) - sub_vig_amount
            direction = "collect"
        else:
            # Players won overall — house loses
            settle_amount = total_player_net + sub_vig_amount
            direction = "pay"

        if abs(settle_amount) < 0.01:
            continue

        settle_amount = abs(settle_amount)

        await db_mod.create_settlement(db, {
            "week_ending": week_ending,
            "counterparty_type": "sub_agent",
            "counterparty_id": sub_id,
            "counterparty_name": sub["name"],
            "amount": settle_amount,
            "direction": direction,
            "vig_amount": sub_vig_amount,
            "notes": f"{len(sub_players)} players, vig earned: ${vig_earned:.2f}, sub keeps: ${sub_vig_amount:.2f}",
        })
        settlements_created += 1
        total_net += settle_amount if direction == "collect" else -settle_amount

        # Create weekly results for each player in this sub
        for p in sub_players:
            player_vig = abs(p["win_loss"]) * vig_rate if p["win_loss"] < 0 else 0
            await db_mod.upsert_weekly_result(db, {
                "player_id": p["id"],
                "sub_agent_id": sub_id,
                "week_ending": week_ending,
                "won_lost": p["win_loss"],
                "vig": player_vig,
                "net": p["win_loss"],
            })

    # 3. Backer settlement
    if total_net != 0:
        # We settle with backer based on our total net
        backer_amount = abs(total_net) * backer_split
        backer_direction = "pay" if total_net > 0 else "collect"

        await db_mod.create_settlement(db, {
            "week_ending": week_ending,
            "counterparty_type": "backer",
            "counterparty_id": None,
            "counterparty_name": "Backer",
            "amount": backer_amount,
            "direction": backer_direction,
            "vig_amount": 0,
            "notes": f"Backer split: {backer_split*100:.0f}% of total net {total_net:.2f}",
        })
        settlements_created += 1

    await db_mod.log_scrape(db, "payday", "success",
                            f"Generated {settlements_created} settlements for {week_ending}",
                            settlements_created)

    return {"ok": True, "count": settlements_created, "total_net": total_net}
