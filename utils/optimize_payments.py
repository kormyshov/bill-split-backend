import copy
from typing import List
from balance_orm import BalanceORM
from typing import NamedTuple
from debt_draft import DebtDraft


class SinglePayment(NamedTuple):
    user_id_from: int
    user_id_to: int
    amount: int
    currency_id: int


class PaymentDraft(NamedTuple):
    user_id: int
    amount: int
    currency_id: int
    debts: List[DebtDraft]


def circle_payment(
        amount: int,
        currency: int,
        user_a: int,
        user_b: int,
        user_c: int) -> List[SinglePayment]:

    return [
        SinglePayment(user_a, user_b, amount, currency),
        SinglePayment(user_b, user_c, amount, currency),
        SinglePayment(user_c, user_a, amount, currency),
    ]

def shift_payment(
        amount: int,
        currency: int,
        user_a: int,
        user_b: int,
        user_c: int) -> List[SinglePayment]:

    if amount < 0:
        return circle_payment(-amount, currency, user_a, user_b, user_c)
    else:
        return circle_payment(amount, currency, user_a, user_c, user_b)

def get_single_payments(balance: List[BalanceORM], user_id: int) -> List[SinglePayment]:
    result = []

    is_optimize = True
    while is_optimize:
        is_optimize = False
        balance.sort(key=lambda x: abs(x.amount))

        for i in range(len(balance)):
            for j in range(i + 1, len(balance)):
                if balance[i].amount * balance[j].amount < 0 and balance[i].currency == balance[j].currency:
                    result.extend(
                        shift_payment(
                            balance[i].amount,
                            balance[i].currency,
                            user_id,
                            balance[i].user_id,
                            balance[j].user_id
                        )
                    )
                    balance[j] = BalanceORM(
                        balance[j].user_id,
                        balance[j].currency,
                        balance[j].amount + balance[i].amount,
                        balance[j].currency_symbol,
                        balance[j].first_and_last_name,
                    )
                    balance[i] = BalanceORM(
                        balance[i].user_id,
                        balance[i].currency,
                        0,
                        balance[i].currency_symbol,
                        balance[i].first_and_last_name,
                    )
                    is_optimize = True
                    break

            if is_optimize:
                break
    return result

def group_by_payments(single_payments: List[SinglePayment]) -> List[PaymentDraft]:
    single_payments.sort(key=lambda x: (x.user_id_from, x.currency_id, x.user_id_to))
    single_payments.append(SinglePayment(-1, -1, 0, -1))

    result: List[PaymentDraft] = []

    cur_user_id = single_payments[0].user_id_from
    cur_currency_id = single_payments[0].currency_id
    cur_debts: List[DebtDraft] = []
    cur_amount = 0

    for single_payment in single_payments:
        if single_payment.user_id_from == cur_user_id and single_payment.currency_id == cur_currency_id:
            cur_amount += single_payment.amount
            if not cur_debts or cur_debts[-1].user_id != single_payment.user_id_to:
                cur_debts.append(DebtDraft(single_payment.user_id_to, single_payment.amount))
            else:
                cur_debts[-1] = DebtDraft(single_payment.user_id_to, single_payment.amount + cur_debts[-1].amount)
        else:
            result.append(PaymentDraft(
                cur_user_id,
                cur_amount,
                cur_currency_id,
                copy.deepcopy(cur_debts),
            ))
            cur_user_id = single_payment.user_id_from
            cur_currency_id = single_payment.currency_id
            cur_debts = [DebtDraft(single_payment.user_id_to, single_payment.amount)]
            cur_amount = single_payment.amount

    return result

def optimize_payments(balance: List[BalanceORM], user_id: int) -> List[PaymentDraft]:
    single_payments = get_single_payments(balance, user_id)
    return group_by_payments(single_payments)
