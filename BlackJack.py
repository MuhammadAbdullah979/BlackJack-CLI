import json
import random
import re
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


STATS_START = "# --- EMBEDDED_STATS_START ---"
STATS_END = "# --- EMBEDDED_STATS_END ---"
CENT = Decimal("0.01")
MIN_BET = Decimal("0.50")
DEFAULT_BALANCE = Decimal("10.00")


def to_money(value):
    """Convert a value to a valid non-negative money amount (2 decimal places)."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("invalid money amount")
    if not amount.is_finite():
        raise ValueError("invalid money amount")
    amount = amount.quantize(CENT, rounding=ROUND_HALF_UP)
    if amount < Decimal("0.00"):
        raise ValueError("negative money amount")
    return amount


def format_money(amount):
    return f"${amount:,.2f}"


def safe_input(prompt):
    try:
        return input(prompt)
    except EOFError:
        print()
        return None
    except KeyboardInterrupt:
        print()
        return None


def load_stats():
    default = {"wins": 0, "losses": 0, "pushes": 0, "balance": float(DEFAULT_BALANCE)}
    try:
        content = Path(__file__).read_text(encoding="utf-8")
        matches = list(re.finditer(
            rf"(?ms)^{re.escape(STATS_START)}\n(.*?)\n^{re.escape(STATS_END)}",
            content,
        ))
        if matches:
            block = matches[-1].group(1)  # use the embedded data block (last occurrence)
            json_text = "\n".join(
                line[2:] if line.startswith("# ") else line[1:] if line.startswith("#") else line
                for line in block.splitlines()
            ).strip()
            if json_text:
                data = json.loads(json_text)
                if isinstance(data, dict):
                    for key in ("wins", "losses", "pushes"):
                        try:
                            default[key] = max(0, int(data.get(key, 0)))
                        except (ValueError, TypeError):
                            default[key] = 0
                    try:
                        default["balance"] = float(to_money(data.get("balance", DEFAULT_BALANCE)))
                    except ValueError:
                        default["balance"] = float(DEFAULT_BALANCE)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return default
    return default


def save_stats(stats):
    try:
        path = Path(__file__)
        content = path.read_text(encoding="utf-8")
        payload = json.dumps(
            {
                "wins": max(0, int(stats.get("wins", 0))),
                "losses": max(0, int(stats.get("losses", 0))),
                "pushes": max(0, int(stats.get("pushes", 0))),
                "balance": float(to_money(stats.get("balance", DEFAULT_BALANCE))),
            },
            indent=2,
        )
        commented = "\n".join(f"# {line}" for line in payload.splitlines())
        new_block = f"{STATS_START}\n{commented}\n{STATS_END}"
        pattern = rf"(?ms)^{re.escape(STATS_START)}\n.*?^{re.escape(STATS_END)}"
        matches = list(re.finditer(pattern, content))
        if matches:
            m = matches[-1]
            content = content[:m.start()] + new_block + content[m.end():]
        else:
            if not content.endswith("\n"):
                content += "\n"
            content += f"\n{new_block}\n"
        path.write_text(content, encoding="utf-8")
    except (OSError, ValueError, TypeError):
        print("(Warning: could not save stats.)")


def print_stats(stats):
    try:
        wins = max(0, int(stats.get("wins", 0)))
        losses = max(0, int(stats.get("losses", 0)))
        pushes = max(0, int(stats.get("pushes", 0)))
    except (ValueError, TypeError):
        wins = losses = pushes = 0
    total = wins + losses + pushes
    print(f"Record - Wins: {wins:,} | Losses: {losses:,} | Pushes: {pushes:,} | Total: {total:,}")


def reset_data(stats):
    stats.clear()
    stats.update({"wins": 0, "losses": 0, "pushes": 0, "balance": float(DEFAULT_BALANCE)})
    save_stats(stats)
    return to_money(DEFAULT_BALANCE)


def get_bet(balance, stats):
    balance = to_money(balance)
    while True:
        print(f"Current balance: {format_money(balance)}")
        raw = safe_input("Enter amount to gamble this round: $")
        if raw is None:
            return None, balance
        stripped = raw.strip()
        if stripped.lower() == "/reset":
            balance = reset_data(stats)
            print("Data reset: wins/losses/pushes cleared and balance set to $10.00.")
            continue
        stripped = stripped.replace(",", "")
        if stripped == "":
            print("Please enter a bet amount.")
            continue
        try:
            bet = to_money(stripped)
        except ValueError:
            print("Please enter a valid amount (e.g. 1.00).")
            continue
        if bet < MIN_BET:
            print(f"Bet must be at least {format_money(MIN_BET)}.")
        elif bet > balance:
            print("You cannot bet more than your current balance.")
        else:
            return bet, balance


def create_deck():
    # Standard 52-card deck: each card is {"rank": str, "suit": str, "value": int}
    suits = ["Clubs", "Diamonds", "Hearts", "Spades"]
    ranks = [
        ("2", 2), ("3", 3), ("4", 4), ("5", 5), ("6", 6), ("7", 7),
        ("8", 8), ("9", 9), ("10", 10), ("Jack", 10), ("Queen", 10),
        ("King", 10), ("Ace", 1),
    ]
    deck = [{"rank": rank, "suit": suit, "value": value} for suit in suits for rank, value in ranks]
    random.shuffle(deck)
    return deck


def hand_value(hand):
    return sum(card["value"] for card in hand)


def card_str(card):
    return f"{card['rank']} of {card['suit']}"


def format_hand(hand, hide_first=False):
    if hide_first:
        return f"[Hidden], {card_str(hand[1])}"
    return ", ".join(card_str(card) for card in hand)


def deal_card(deck):
    if not deck:
        deck.extend(create_deck())
    return deck.pop()


def player_turn(deck, player_hand):
    while True:
        total = hand_value(player_hand)
        print(f"\nYour hand: {format_hand(player_hand)} (total: {total})")

        if total > 21:
            print("You busted!")
            return total
        if total == 21:
            print("21!")
            return total

        choice = safe_input("Would you like to hit or stand? [h/s]: ")
        if choice is None:
            print("Input closed. Standing by default.")
            return total
        choice = choice.strip().lower()
        if choice in ("h", "hit"):
            card = deal_card(deck)
            player_hand.append(card)
            print(f"You drew: {card_str(card)}")
        elif choice in ("s", "stand"):
            print(f"You stand with {total}.")
            return total
        else:
            print("Invalid input. Please enter 'h' to hit or 's' to stand.")


def dealer_turn(deck, dealer_hand):
    print(f"\nDealer's hand: {format_hand(dealer_hand)} (total: {hand_value(dealer_hand)})")
    while hand_value(dealer_hand) < 17:
        card = deal_card(deck)
        dealer_hand.append(card)
        print(f"Dealer drew: {card_str(card)}")
        print(f"Dealer's hand: {format_hand(dealer_hand)} (total: {hand_value(dealer_hand)})")

    total = hand_value(dealer_hand)
    if total > 21:
        print("Dealer busted!")
    else:
        print(f"Dealer stands with {total}.")
    return total


def determine_winner(player_total, dealer_total):
    if player_total > 21:
        return "dealer"
    if dealer_total > 21:
        return "player"
    if player_total > dealer_total:
        return "player"
    if dealer_total > player_total:
        return "dealer"
    return "push"


def play_round():
    deck = create_deck()
    player_hand = [deal_card(deck), deal_card(deck)]
    dealer_hand = [deal_card(deck), deal_card(deck)]

    print("\n=== New Round ===")
    print(f"Dealer shows: {format_hand(dealer_hand, hide_first=True)}")

    # Check for natural blackjack scenarios
    player_blackjack = hand_value(player_hand) == 21
    dealer_blackjack = hand_value(dealer_hand) == 21
    if player_blackjack or dealer_blackjack:
        print(f"Your hand: {format_hand(player_hand)} (total: {hand_value(player_hand)})")
        print(f"Dealer's hand: {format_hand(dealer_hand)} (total: {hand_value(dealer_hand)})")
        if player_blackjack and dealer_blackjack:
            print("Both have blackjack! It's a push.")
            return "push"
        elif player_blackjack:
            print("Blackjack! You win!")
            return "player"
        else:
            print("Dealer has blackjack. You lose.")
            return "dealer"

    player_total = player_turn(deck, player_hand)

    if player_total <= 21:
        dealer_total = dealer_turn(deck, dealer_hand)
    else:
        dealer_total = hand_value(dealer_hand)
        print(f"Dealer reveals: {format_hand(dealer_hand)} (total: {dealer_total})")

    result = determine_winner(player_total, dealer_total)
    print()
    if result == "player":
        print("You win!")
    elif result == "dealer":
        print("Dealer wins.")
    else:
        print("It's a push (tie).")
    return result


def main():
    try:
        stats = load_stats()
        print("Welcome to Blackjack (CLI)!")
        print("Rules: Get as close to 21 as possible without going over.")
        print("Dealer hits until 17 or higher. Aces count as 1.")
        print_stats(stats)

        try:
            balance = to_money(stats.get("balance", DEFAULT_BALANCE))
        except ValueError:
            balance = DEFAULT_BALANCE

        if balance < MIN_BET:
            print("Buddy you suck at this game just give up")
            balance = to_money("0.99")
            stats["balance"] = float(balance)
            save_stats(stats)
            return

        stats["balance"] = float(balance)
        save_stats(stats)

        while True:
            if balance < MIN_BET:
                print("Buddy you suck at this game just give up")
                balance = to_money("0.99")
                stats["balance"] = float(balance)
                save_stats(stats)
                break

            bet, balance = get_bet(balance, stats)
            if bet is None:
                stats["balance"] = float(balance)
                save_stats(stats)
                print("\nInput closed. Progress saved. Thanks for playing!")
                break

            print(f"You gambled: {format_money(bet)}")

            result = play_round()
            if result == "player":
                stats["wins"] = int(stats.get("wins", 0)) + 1
                balance = to_money(balance + bet)
                print(f"You won! You gained {format_money(bet)}. Balance: {format_money(balance)}")
            elif result == "dealer":
                stats["losses"] = int(stats.get("losses", 0)) + 1
                balance = to_money(balance - bet)
                print(f"You lost. You lost {format_money(bet)}. Balance: {format_money(balance)}")
            else:
                stats["pushes"] = int(stats.get("pushes", 0)) + 1
                print(f"It's a push. Your bet is returned. Balance: {format_money(balance)}")

            stats["balance"] = float(balance)
            save_stats(stats)
            print_stats(stats)

            while True:
                again = safe_input("\nPlay another round? [y/n]: ")
                if again is None:
                    stats["balance"] = float(balance)
                    save_stats(stats)
                    print("Thanks for playing!")
                    print(f"Final balance: {format_money(balance)}")
                    print("Final record:")
                    print_stats(stats)
                    return
                cmd = again.strip().lower()
                if cmd == "/reset":
                    balance = reset_data(stats)
                    print("Data reset: wins/losses/pushes cleared and balance set to $10.00.")
                    print_stats(stats)
                    continue
                if cmd in ("y", "yes"):
                    break
                stats["balance"] = float(balance)
                save_stats(stats)
                print("Thanks for playing!")
                print(f"Final balance: {format_money(balance)}")
                print("Final record:")
                print_stats(stats)
                return
    except KeyboardInterrupt:
        print("\n\nInterrupted. Saving progress...")
        try:
            if 'stats' in locals() and 'balance' in locals():
                stats["balance"] = float(to_money(balance))
                save_stats(stats)
                print(f"Saved balance: {format_money(to_money(balance))}")
        except Exception:
            pass
        print("Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()

# --- EMBEDDED_STATS_START ---
# {
#   "wins": 0,
#   "losses": 0,
#   "pushes": 0,
#   "balance": 0.5
# }
# --- EMBEDDED_STATS_END ---
