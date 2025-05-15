import time
from fints.client import FinTS3PinTanClient, NeedTANResponse, ResponseStatus, SEPAAccount
from fints.utils import minimal_interactive_cli_bootstrap
import requests

from config import Config, Destination




def do_transfer(config: Config, client: FinTS3PinTanClient, source_account: SEPAAccount, destination: Destination, amount: float):
    print("transfering " + str(amount) + " EUR to " + destination.name + " (" + destination.iban + ")")
    
    minimal_interactive_cli_bootstrap(client)

    transfer = client.simple_sepa_transfer(
        account=source_account,
        iban=destination.iban, 
        bic=destination.bic, 
        recipient_name=config.source.fints.account_name, 
        amount=amount, 
        account_name=config.source.fints.account_name, 
        reason="Automatic Transfer "+str(round(time.time())), 
        instant_payment=True
    )

    if isinstance(transfer, NeedTANResponse):
        print("Tan not suported in this app")
        raise "Tan not suported in this app"
    
    print(transfer.status)
    print(transfer.responses)

    if transfer.status == ResponseStatus.ERROR:
        raise "Transfer failed\n\n"+str(transfer.responses)


def main():
    # Load the configuration
    config = Config()

    # Create the FinTS client
    client = FinTS3PinTanClient(
        bank_identifier=config.source.fints.blz,
        user_id=config.source.fints.username,
        pin=config.source.fints.password,
        server=config.source.fints.host,
        product_id=config.source.fints.product_id
    )

    source_account: SEPAAccount = SEPAAccount(
        iban=config.source.fints.iban,
        bic=config.source.fints.bic,
        accountnumber=config.source.fints.iban[-10:],
        subaccount=None,
        blz=config.source.fints.blz
    )
    
    # minimal_interactive_cli_bootstrap(client)
    
    with client:
        if client.init_tan_response:
            client.send_tan(client.init_tan_response, input("Tan (or enter if just confirm): "))

        # accounts = client.get_sepa_accounts()
        # for account in accounts:
        #     print(f"Account: {account}")
        #     if account.iban == config.source.fints.iban:
        #         source_account = account
        #         break

    time.sleep(1)

    while True:
        try:
            if config.source.is_interval_reached():
                with client:
                    # Get the balance of the source account
                    balance = client.get_balance(source_account)
                    print(f"Balance: {balance}")

                    # Check if the balance is above the minimum balance
                    if balance < config.source.min_balance:
                        print(f"Balance {balance} is below minimum {config.source.min_balance}. No transfer possible.")
                        continue

                    destination_balances = requests.get(config.destinations_url).json()

                    sum_delta = 0
                    for destination in config.destinations:
                        if destination.name not in destination_balances:
                            print(f"Destination {destination.name} not found in the response.")
                            continue

                        destination_balance = destination_balances[destination.name]
                        print(f"Destination {destination.name} balance: {destination_balance}")

                        if destination_balance > destination.min_balance:
                            print(f"Destination {destination.name} balance is above minimum. No transfer needed.")
                            continue

                        delta = round(destination.min_balance - destination_balance)

                        if delta < config.source.min_transaction:
                            print(f"Delta {delta} is below minimum transaction. No transfer needed.")
                            continue

                        do_transfer(config, client, source_account, destination, delta)
                        
                        sum_delta += delta
                            
                        time.sleep(10)

                    print(f"Sum of deltas: {sum_delta}")

                    sum_surplus_transfered = 0
                    if config.source.surplus_threshold and balance - sum_delta > config.source.surplus_threshold and (balance - sum_delta) - config.source.min_balance:
                        print(f"Surplus {balance - sum_delta} is above threshold {config.source.surplus_threshold}. Distributing surplus.")

                        surplus = round(balance - sum_delta - config.source.min_balance)

                        for destination in config.destinations:
                            delta = round(surplus * destination.surplus_percentage)

                            if delta < config.source.min_transaction:
                                print(f"Delta {delta} is below minimum transaction. No transfer needed.")
                                continue

                            do_transfer(config, client, source_account, destination, delta)

                            sum_surplus_transfered += delta
                            
                            time.sleep(10)


                    print(f"Total surplus transfered: {sum_surplus_transfered}")
                    print(f"Total transfered: {sum_delta + sum_surplus_transfered}")
                    print(f"New balance: {balance - sum_delta - sum_surplus_transfered}")

            time.sleep(60*30)

        except KeyboardInterrupt:
            print("Exiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(60*5)
            continue

if __name__ == "__main__":
    main()