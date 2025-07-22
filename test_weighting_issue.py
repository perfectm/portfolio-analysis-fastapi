#!/usr/bin/env python3

# Test calculation to verify the weighting issue
individual_profits = [64727.40, 69934.96, 60735.28]
total_individual = sum(individual_profits)
equal_weight = 1/3
weighted_total = sum(p * equal_weight for p in individual_profits)

print(f"Individual profits: {individual_profits}")
print(f"Sum of individual: ${total_individual:,.2f}")
print(f"With 1/3 weight each: ${weighted_total:,.2f}")
print(f"Blended result from UI: $65,132.55")
print(f"Difference: ${abs(total_individual - 65132.55):,.2f}")

print("\nAnalysis:")
print("The current implementation multiplies each portfolio's P/L by its weight (1/3)")
print("This reduces the total profit to 1/3 of what it should be")
print("Expected behavior: Combine full P/L from all strategies")
