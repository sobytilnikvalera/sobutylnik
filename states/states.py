from aiogram.fsm.state import State, StatesGroup

class ProfileSetup(StatesGroup):
    waiting_age = State()
    waiting_bio = State()

class CreateListing(StatesGroup):
    waiting_photo = State()
    waiting_title = State()
    waiting_description = State()
    waiting_drinks = State()
    waiting_snacks = State()
    waiting_location = State()
    waiting_search_location = State()
    waiting_max_people = State()
    waiting_confirm = State()

class BrowseAnketas(StatesGroup):
    browsing = State()

class LeaveReview(StatesGroup):
    waiting_rating = State()
    waiting_text = State()

class FeedbackStates(StatesGroup):
    waiting_feedback = State()
