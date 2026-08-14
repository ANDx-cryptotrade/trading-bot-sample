"""Trading logic. Here the decision is always BUY - build from here to add your own strategy."""

# Fixed USDT amount to spend on each run.
TRADE_USD = 7.00


def decide(price):
    """Return the action for this run. Always buys (price is unused, here for easy upgrades)."""
    action = "BUY"
    return action

