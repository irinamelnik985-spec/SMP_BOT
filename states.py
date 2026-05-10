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


class TicketStates(StatesGroup):
    choosing_type = State()
    waiting_offender = State()
    waiting_complaint_text = State()
    waiting_complaint_photo = State()
    waiting_question_text = State()
    waiting_question_photo = State()
    waiting_reply_text = State()
