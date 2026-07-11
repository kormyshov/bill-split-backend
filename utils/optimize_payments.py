import copy
import heapq
from collections import defaultdict
from typing import List
from balance_orm import BalanceORM
from typing import NamedTuple
from debt_draft import DebtDraft
from expense_draft import ExpenseDraft


class SinglePayment(NamedTuple):
    user_id_from: int
    user_id_to: int
    amount: int
    currency_id: int


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

    pos_heaps: dict[int, list] = defaultdict(list)
    neg_heaps: dict[int, list] = defaultdict(list)

    for b in balance:
        if b.amount == 0:
            continue
        item = (abs(b.amount), b.user_id, b.amount, b.currency_symbol, b.first_and_last_name)
        if b.amount > 0:
            heapq.heappush(pos_heaps[b.currency], item)
        else:
            heapq.heappush(neg_heaps[b.currency], item)

    for currency in pos_heaps:
        neg_heap = neg_heaps.get(currency)
        if not neg_heap:
            continue
        pos_heap = pos_heaps[currency]

        while pos_heap and neg_heap:
            pos = heapq.heappop(pos_heap)
            neg = heapq.heappop(neg_heap)

            if pos[2] >= -neg[2]:
                result.extend(
                    shift_payment(neg[2], currency, user_id, neg[1], pos[1])
                )
                remainder = pos[2] + neg[2]
                if remainder > 0:
                    heapq.heappush(pos_heap, (remainder, pos[1], remainder, pos[3], pos[4]))
            else:
                result.extend(
                    shift_payment(pos[2], currency, user_id, pos[1], neg[1])
                )
                remainder = pos[2] + neg[2]
                if remainder < 0:
                    heapq.heappush(neg_heap, (-remainder, neg[1], remainder, neg[3], neg[4]))

    return result

def group_by_payments(single_payments: List[SinglePayment]) -> List[ExpenseDraft]:
    single_payments.sort(key=lambda x: (x.user_id_from, x.currency_id, x.user_id_to))
    single_payments.append(SinglePayment(-1, -1, 0, -1))

    result: List[ExpenseDraft] = []

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
            result.append(ExpenseDraft(
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

def optimize_payments(balance: List[BalanceORM], user_id: int) -> List[ExpenseDraft]:
    single_payments = get_single_payments(balance, user_id)
    return group_by_payments(single_payments)
