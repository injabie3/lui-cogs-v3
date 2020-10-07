KEY_BDAY_CHANNEL = "birthdayChannel"
KEY_BDAY_ROLE = "birthdayRole"
KEY_BDAY_USERS = "birthdayUsers"
KEY_BDAY_MONTH = "birthdateMonth"
KEY_BDAY_DAY = "birthdateDay"
KEY_IS_ASSIGNED = "isAssigned"
KEY_DATE_SET_MONTH = "dateAssignedMonth"
KEY_DATE_SET_DAY = "dateAssignedDay"

BASE_GUILD_MEMBER = {
    KEY_BDAY_DAY: None,
    KEY_BDAY_MONTH: None,
    KEY_DATE_SET_DAY: None,
    KEY_DATE_SET_MONTH: None,
    KEY_IS_ASSIGNED: False,
}

BASE_GUILD = {KEY_BDAY_CHANNEL: None, KEY_BDAY_ROLE: None}

CANNED_MESSAGES = [
    "Wow look, it's {}'s birthday today! Happy birthday, hope you have a good one!",
    "お誕生日おめでとう、{}! (TL note: Happy birthday!)",
    "Wow, would you look at that, it's {}'s birthday. Time to wish them a happy birthday!",
    "Hey everyone! it's {} birthday, come and wish them a happy birthday!",
    "Wow {}, happy birthday! How does it feel to be more boomer than you were yesterday?",
]
