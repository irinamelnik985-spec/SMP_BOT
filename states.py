from aiogram.fsm.state import State, StatesGroup


class FormStates(StatesGroup):
    waiting_age = State()
    waiting_nickname = State()
    waiting_playtime = State()
    waiting_experience = State()
    waiting_plans = State()
    waiting_source = State()


class PanelStates(StatesGroup):
    waiting_me_text = State()
    waiting_wl_add = State()
    waiting_wl_remove = State()
    waiting_reject_reason = State()
    waiting_broadcast_text = State()


class RulesStates(StatesGroup):
    reading = State()
