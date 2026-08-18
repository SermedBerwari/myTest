from src.collectors.fpl_client import FPLClient


def main() -> None:
    parser = argparse.ArgumentParser(description='Run test_fpl_connection.py.')
    parser.parse_args()
    print("=" * 60)
    print("FPL API CONNECTION TEST")
    print("=" * 60)

    try:
        with FPLClient() as client:
            print("\nConnecting to official FPL API...")

            data = client.get_bootstrap()

            print("\nConnection successful!")

            print(f"Gameweeks : {len(data.get('events', []))}")
            print(f"Teams     : {len(data.get('teams', []))}")
            print(f"Players   : {len(data.get('elements', []))}")
            print(
                f"Positions : {len(data.get('element_types', []))}"
            )

            if data.get("events"):
                current = next(
                    (
                        event
                        for event in data["events"]
                        if event.get("is_current")
                    ),
                    None,
                )

                next_gameweek = next(
                    (
                        event
                        for event in data["events"]
                        if event.get("is_next")
                    ),
                    None,
                )

                print()

                if current:
                    print(
                        f"Current GW: "
                        f"{current.get('id')} "
                        f"({current.get('name')})"
                    )
                else:
                    print("Current GW: None")

                if next_gameweek:
                    print(
                        f"Next GW   : "
                        f"{next_gameweek.get('id')} "
                        f"({next_gameweek.get('name')})"
                    )
                else:
                    print("Next GW   : None")

    except Exception as exc:
        print("\nFPL API connection FAILED.")
        print(f"Error: {exc}")

        raise


if __name__ == "__main__":
    main()

