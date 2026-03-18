def apply_scenario(base_data, scenario):

    new_data = base_data.copy()

    # Simple rules (can be expanded later)
    if "increase_revenue" in scenario:
        new_data["revenue_growth"] *= (1 + scenario["increase_revenue"])

    if "reduce_debt" in scenario:
        new_data["debt_ratio"] *= (1 - scenario["reduce_debt"])

    if "improve_liquidity" in scenario:
        new_data["current_ratio"] *= (1 + scenario["improve_liquidity"])

    return new_data