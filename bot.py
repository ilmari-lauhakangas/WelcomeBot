# Welcome to WelcomeBot.
# Find source, documentation, etc here: https://github.com/shaunagm/WelcomeBot/
# Licensed https://creativecommons.org/licenses/by-sa/2.0/

# Import some necessary libraries.
import socket
import sys
import time
import random
import re
import select
import os.path
import json
import signal

# To configure bot, please make changes in bot_settings.py
import bot_settings as settings


#####################
# Class Definitions #
#####################

# Defines a bot
class Bot(object):
    def __init__(self, botnick=settings.botnick, welcome_message=settings.welcome_message,
                 nick_source=settings.nick_source, wait_time=settings.wait_time,
                 hello_list=settings.hello_list, help_list=settings.help_list,
                 bots=settings.bots):
        self.botnick = botnick
        self.welcome_message = welcome_message
        self.nick_source = nick_source
        self.wait_time = wait_time
        self.known_nicks = set()
        self.known_bots = bots
        self.newcomers = []
        self.hello_regex = re.compile(get_regex(hello_list, botnick), re.I)  # Regexed version of hello list
        self.help_regex = re.compile(get_regex(help_list, botnick), re.I)  # Regexed version of help list

    def add_known_nick(self, nick):
        """Add the current newcomer's nick to nicks.csv and known_nicks."""
        self.known_nicks.add(nick)
        self.save_nicks()

    def add_newcomer(self, nick):
        self.newcomers.append(NewComer(nick))

    def save_nicks(self):
        with open(self.nick_source, 'w') as nick_file:
            json.dump(
                {'nicks': list(self.known_nicks)},
                nick_file,
                ensure_ascii=False,
                encoding='utf-8',
                indent=4,
            )

    def load_nicks(self):
        try:
            with open(self.nick_source, 'r') as nick_file:
                doc = json.load(nick_file, encoding='utf-8')
                self.known_nicks.update(doc['nicks'])
        except IOError:  # File not found; ignore
            print('{} not found; no nicks loaded', format(self.nick_source))


class NewComer(object):
    def __init__(self, nick):
        self.nick = nick
        self.clean_nick = clean_nick(self.nick)
        self.born = time.time()

    def around_for(self):
        return time.time() - self.born


#####################
# Startup Functions #
#####################

# Creates a socket that will be used to send and receive messages,
# then connects the socket to an IRC server and joins the channel.
def irc_start(server):  # pragma: no cover  (this excludes this function from testing)
    ircsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ircsock.connect((server, 6667))  # Here we connect to server using port 6667.
    return ircsock


def msg_send(ircsock, msg):
    ircsock.send(msg.encode('utf-8'))


def join_irc(ircsock, botnick, channel):
    msg_send(ircsock, "USER {0} {0} {0} :This is http://falcon.readthedocs.io/en/stable/"
                      "greeter bot.\n".format(botnick))  # bot authentication
    msg_send(ircsock, "NICK {}\n".format(botnick))  # Assign the nick to the bot.
    if os.path.isfile("password.txt"):
        with open("password.txt", 'r') as f:
            password = f.read()
            if settings.registered is True:
                msg_send(ircsock, "PRIVMSG {} {} {} {}".format("NickServ", "IDENTIFY", botnick, password))
    msg_send(ircsock, "JOIN {} \n".format(channel))  # Joins channel


# Reads the messages from the server and adds them to the Queue and prints
# them to the console. This function will be run in a thread, see below.
def msg_handler(ircsock):  # pragma: no cover  (this excludes this function from testing)
    new_msg = ircsock.recv(2048).decode('utf-8')  # receive data from the server
    new_msg = new_msg.strip('\n\r')  # removing any unnecessary linebreaks
    print(new_msg)  # TODO Potentially make this a log instead?
    return new_msg


# Called by bot on startup.  Builds a regex that matches one of the options + (space) botnick.
def get_regex(options, botnick):
    pattern = "({}).({})".format('|'.join(options), botnick)
    return pattern


#####################
# General Functions #
#####################

# Welcomes the "person" passed to it.
def welcome_nick(bot, newcomer, ircsock, channel, channel_greeters):
    welcome = bot.welcome_message.format(
        newcomer=newcomer,
        greeter_string=greeter_string(channel_greeters)
    )

    command = "PRIVMSG {0} :{1}\n".format(channel, welcome)
    msg_send(ircsock, command)


# Checks and manages the status of newcomers.
def process_newcomers(bot, ircsock, channel, greeters, welcome=True):
    newcomers = [p for p in bot.newcomers if p.around_for() > bot.wait_time]
    for person in newcomers:
        if welcome:
            welcome_nick(bot, person.nick, ircsock, channel, greeters)

        bot.add_known_nick(person.clean_nick)
        bot.newcomers.remove(person)


# Checks for messages.
def parse_messages(ircmsg):
    try:
        actor = ircmsg.split(":")[1].split("!")[0]  # and get the nick of the msg sender
        return " ".join(ircmsg.split()), actor
    except IndexError:
        return None, None


# Cleans a nickname of decorators/identifiers
def clean_nick(nick):
    nick = nick.rstrip('_1234567890')
    nick = nick.split('|', 1)[0]  # Returns same nick if '|' is absent
    nick = nick.lower()

    return nick


# Parses messages and respond to them appropriately.
def message_response(bot, ircmsg, actor, ircsock, channel, greeters):
    clean_actor = clean_nick(actor)
    clean_newcomers = [person.clean_nick for person in bot.newcomers]

    # if someone other than a newcomer or bot speaks into the channel
    if ircmsg.find("PRIVMSG " + channel) != -1 and clean_actor not in bot.known_bots + clean_newcomers:
        process_newcomers(bot, ircsock, channel, greeters, welcome=False)  # Process/check newcomers without welcoming them

    # if someone (other than the bot) joins the channel
    if ircmsg.find("JOIN " + channel) != -1 and actor != bot.botnick:
        if clean_actor not in bot.known_bots + bot.known_nicks + clean_newcomers:
            bot.add_newcomer(actor)

    # if someone changes their nick while still in newcomers update that nick
    if ircmsg.find("NICK :") != -1 and actor != bot.botnick:
        for person in bot.newcomers:  # if that person was in the newlist
            if person.nick == actor:
                person.nick = ircmsg.split(":")[2]  # update to new nick (and clean up the nick)
                person.clean_nick = clean_nick(person.nick)

    # If someone parts or quits the #channel...
    if ircmsg.find("PART " + channel) != -1 or ircmsg.find("QUIT") != -1:
        for person in bot.newcomers:  # and that person is on the newlist
            if clean_actor == person.clean_nick:
                bot.newcomers.remove(person)  # remove them from the list

    # If someone talks to (or refers to) the bot.
    if bot.botnick.lower() in ircmsg.lower() and "PRIVMSG".lower() in ircmsg.lower():
        if bot.hello_regex.search(ircmsg):
            bot_hello(random.choice(settings.hello_list), actor, ircsock, channel)
        elif bot.help_regex.search(ircmsg):
            bot_help(ircsock, channel)

    # If someone tries to change the wait time...
    if ircmsg.find(bot.botnick + " --wait-time ") != -1:
        # call this to check and change it
        bot.wait_time = wait_time_change(actor, ircmsg, ircsock, channel, greeters, bot)

    # If the server pings us then we've got to respond!
    if ircmsg.find("PING :") != -1:
        pong(ircsock, ircmsg)


#########################################################
# Bot Response Functions (called by message_response()) #
#########################################################

# Responds to a user that inputs "Hello Mybot".
def bot_hello(greeting, actor, ircsock, channel):
    msg_send(ircsock, "PRIVMSG {0} :{1} {2}\n".format(channel, greeting, actor))


# Explains what the bot is when queried.
def bot_help(ircsock, channel):
    msg_send(ircsock, "PRIVMSG {} :I'm a bot!  I'm a fork of shauna's welcomebot, "
                      "you can checkout my internals and contribute here: "
                      "https://github.com/falconry/WelcomeBot"
                      ".\n".format(channel))


# Returns a grammatically correct string of the channel_greeters.
def greeter_string(greeters):
    greeterstring = ', '.join(greeters[:-1])

    if len(greeters) > 2:
        greeterstring += ", and {}".format(greeters[-1])
    elif len(greeters) == 2:
        greeterstring += " and {}".format(greeters[-1])

    return greeterstring


# Changes the wait time from the channel.
def wait_time_change(actor, ircmsg, ircsock, channel, channel_greeters, bot):
    for admin in channel_greeters:
        if actor == admin:
            finder = re.search(r'\d\d*', re.search(r'--wait-time \d\d*', ircmsg).group())
            msg_send(ircsock, "PRIVMSG {0} :{1} the wait time is changing to {2} "
                              "seconds.\n".format(channel, actor, finder.group()))
            new_wait_time = int(finder.group())
            return new_wait_time
    msg_send(ircsock, "PRIVMSG {0} :{1} you are not authorized to make that "
                      "change. Please contact one of the channel greeters, like {2}, for "
                      "assistance.\n".format(channel, actor, greeter_string(channel_greeters)))
    unchanged_wait_time = bot.wait_time
    return unchanged_wait_time


# Responds to server Pings.
def pong(ircsock, ircmsg):
    response = "PONG :" + ircmsg.split("PING :")[1] + "\n"
    msg_send(ircsock, response)


def signal_handler(signum, frame):
    print('Exit')
    sys.exit(0)


######################
# The main function. #
######################
def main():
    signal.signal(signal.SIGINT, signal_handler)

    ircsock = irc_start(settings.server)
    join_irc(ircsock, settings.botnick, settings.channel)

    bot = Bot()
    bot.load_nicks()

    while 1:  # Loop forever
        wait_time = bot.wait_time

        if bot.newcomers:
            wait_time -= max([person.around_for() for person in bot.newcomers])

        if wait_time < 0:
            wait_time = 1

        ready_to_read, _, _ = select.select([ircsock], [], [], wait_time)  # wlist, xlist are ignored here

        process_newcomers(bot, ircsock, settings.channel, settings.channel_greeters)

        if ready_to_read:
            ircmsg = msg_handler(ircsock)  # gets message from ircsock
            ircmsg, actor = parse_messages(ircmsg)  # parses it or returns None
            if ircmsg is not None:  # If we were able to parse it
                # Respond to the parsed message
                message_response(bot, ircmsg, actor, ircsock, settings.channel, settings.channel_greeters)


if __name__ == "__main__":
    sys.exit(main())
