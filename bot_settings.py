# Replace these default settings with your own personal settings

# IRC configuration
channel = "#falconframework"
botnick = "elaenor"
server = "irc.freenode.net"
registered = False

# Bot behavior
wait_time = 60
channel_greeters = ["kgriffs", "jvrbanac"]
nick_source = "/opt/WelcomeBot/nicks.csv"

# Bot text
hello_list = ["hello", "hi", "hey", "yo", "sup"]
help_list = ["help", "info", "faq", "explain_yourself"]
welcome_message = ("Welcome {newcomer}! The channel is pretty quiet "
                   "right now, so I thought I'd say "
                   "hello, and ping some people that "
                   "you're here (like {greeter_string}). "
                   "I'm a bot! If no one responds for "
                   "a while, try visiting our discussion group at "
                   "https://groups.google.com/d/forum/falconframework "
                   "or just try coming back later.")
