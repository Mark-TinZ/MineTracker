from aiogram.fsm.state import State, StatesGroup

class TicketStates(StatesGroup):
    """FSM состояния для создания тикетов в поддержку."""
    waiting_for_message = State()
