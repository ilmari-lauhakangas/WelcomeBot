# Yay tests!

# TODO(kgriffs): These are wildly out of date; redo tests with pytest and tox

import json
import unittest
import time

import bot as botcode
# To configure bot, please make changes in bot_settings.py
import bot_settings as settings


################
# FAKE IRCSOCK #
################

class FakeIrcConn(object):
    def __init__(self):
        self.sent_messages = []

    def send(self, msg):
        self.sent_messages.append(msg)

    def sent_message(self):
        return self.sent_messages[-1]

    def has_sent_message(self):
        return bool(self.sent_messages)


def fake_irc_start():
    ircconn = FakeIrcConn()
    return ircconn


class TestBotClass(unittest.TestCase):
    def setUp(self):
        self.bot = botcode.Bot(None, '', nick_source='test_nicks.json')

    def test_nick_source(self):
        self.assertEqual(self.bot.nick_source, 'test_nicks.json')

    def test_known_nicks_setup(self):
        self.bot.load_nicks()
        self.assertEqual(self.bot.known_nicks, {'Alice', 'Bob'})

    def test_wait_time(self):
        self.assertEqual(self.bot.wait_time, settings.wait_time)

    def test_custom_wait_time(self):
        bot = botcode.Bot(None, '', wait_time=30)
        self.assertEqual(bot.wait_time, 30)

    def test_newcomers_setup(self):
        self.assertEqual(self.bot.newcomers, [])

    def test_add_nick_to_set(self):
        self.bot.known_nicks = {'Fluffy', 'Spot'}
        self.bot.add_known_nick('Roger')
        self.assertEqual(self.bot.known_nicks, {'Fluffy', 'Spot', 'Roger'})

    def test_add_nick_to_json(self):
        self.bot.load_nicks()
        self.bot.add_known_nick('Roger')
        with open('test_nicks.json', 'rb') as nick_file:
            doc = json.load(nick_file)
        known_nicks = set(doc['nicks'])
        self.assertEqual(known_nicks, {'Alice', 'Bob', 'Roger'})

    def tearDown(self):
        with open('test_nicks.json', 'w') as nick_file:
            json.dump({'nicks': ['Alice', 'Bob']}, nick_file)
        self.bot.known_nicks.clear()


class TestNewComerClass(unittest.TestCase):
    def setUp(self):
        self.new_comer = botcode.NewComer('Nancy')

    def test_newcomer_init_nick(self):
        self.assertEqual(self.new_comer.nick, 'Nancy')

    def test_newcomer_init_born(self):
        new_comer = botcode.NewComer('Baby')
        time.sleep(0.01)
        self.assertAlmostEqual(new_comer.born, time.time() - .01, places=2)

    def test_newcomer_around_for(self):
        new_comer = botcode.NewComer('Shauna')
        time.sleep(0.01)
        self.assertAlmostEqual(new_comer.around_for(), .01, places=2)


class TestJoinIRC(unittest.TestCase):
    def setUp(self):
        self.ircsock = fake_irc_start()
        self.bot = botcode.Bot(None, '')

    def test_sent_messages(self):
        channels = [channel for channel in settings.channels if settings.channels[channel]['join']]
        channels_str = ','.join(channels)
        botcode.join_irc(self.ircsock, settings.botnick, channels_str)
        expected = ["USER {0} {0} {0} :This is http://falcon.readthedocs.io/en/stable/"
                    "greeter bot.\n".format(self.bot.nick),
                    'NICK {}\n'.format(self.bot.nick), 'JOIN {} \n'.format(channels_str)]
        self.assertEqual(self.ircsock.sent_messages, expected)


class TestProcessNewcomers(unittest.TestCase):
    def setUp(self):
        self.bot = botcode.Bot(None, '', nick_source='test_nicks.json', wait_time=.1)
        self.bot.add_newcomer('Harry')
        self.bot.add_newcomer('Hermione')
        time.sleep(.15)
        self.bot.add_newcomer('Ron')
        self.ircsock = fake_irc_start()

    def test_check_new_newcomers(self):
        botcode.process_newcomers(self.bot, ircconn=self.ircsock, welcome=False)
        self.assertEqual(len(self.bot.newcomers), 1)

    def test_check_new_known_nicks(self):
        botcode.process_newcomers(self.bot, ircconn=self.ircsock, welcome=False)
        self.assertEqual(self.bot.known_nicks, {'Alice', 'Bob', 'Harry', 'Hermione'})

    def test_welcome_nick(self):
        botcode.process_newcomers(self.bot, ircconn=self.ircsock, welcome=True)
        self.assertEqual(self.ircsock.sent_message(),
                         "PRIVMSG {0} :Welcome Hermione!  The channel is pretty quiet right now, so I thought I'd say hello, and ping some people (like {1}) that you're here.  If no one responds for a while, try emailing us at hello@openhatch.org or just try coming back later.  FYI, you're now on my list of known nicknames, so I won't bother you again.\n".format(
                             self.bot.channel, self.bot.greeters_string))

    def tearDown(self):
        with open('test_nicks.json', 'w') as nick_file:
            json.dump({'nicks': ['Alice', 'Bob']}, nick_file)


class TestParseMessages(unittest.TestCase):
    def test_good_string(self):
        ircmsg, actor = botcode.parse_messages(
            ":vader!darth@darkside.org PRIVMSG #deathstar : I find your lack of faith disturbing")
        self.assertEqual([ircmsg, actor],
                         [':vader!darth@darkside.org PRIVMSG #deathstar : I find your lack of faith disturbing',
                          'vader'])

    def test_bad_string(self):
        ircmsg, actor = botcode.parse_messages("we should probably replace this with a bad string more likely to occur")
        self.assertEqual([ircmsg, actor], [None, None])


class TestMessageResponse(unittest.TestCase):
    def setUp(self):
        self.bot = botcode.Bot('test_nicks.csv')
        botcode.NewComer('Chappe', self.bot)
        self.ircsock = fake_irc_start()

    def test_newcomer_speaking(self):
        botcode.message_response(self.bot, "~q@r.m.us PRIVMSG {} :hah".format(settings.channel), "Chappe",
                                 ircconn=self.ircsock, channel=settings.channel,
                                 greeters=settings.channel_greeters)  # Standard message by newcomer
        nicklist = [i.nick for i in self.bot.newcomers]  # Makes a list of newcomers nicks for easy asserting
        self.assertEqual(nicklist, ['Chappe'])

    def test_oldtimer_speaking(self):
        botcode.message_response(self.bot, "~q@r.m.us PRIVMSG {} :hah".format(settings.channel), "Alice",
                                 ircconn=self.ircsock, channel=settings.channel,
                                 greeters=settings.channel_greeters)  # Standard message by oldtimer
        nicklist = [i.nick for i in self.bot.newcomers]  # Makes a list of newcomers nicks for easy asserting
        self.assertEqual(nicklist, [])

    def test_join(self):
        botcode.message_response(self.bot, "JOIN {} right now!".format(settings.channel), "Shauna",
                                 ircconn=self.ircsock, channel=settings.channel,
                                 greeters=settings.channel_greeters)  # Replace with actual ping message
        self.assertEqual(self.bot.newcomers[1].nick, 'Shauna')

    def test_part(self):
        botcode.message_response(self.bot, "JOIN {} right now!".format(settings.channel), "Shauna",
                                 ircconn=self.ircsock, channel=settings.channel,
                                 greeters=settings.channel_greeters)  # Replace with actual ping message
        self.assertEqual(len(self.bot.newcomers), 2)
        botcode.message_response(self.bot, "PART {}".format(settings.channel), "Shauna", ircconn=self.ircsock,
                                 channel=settings.channel,
                                 greeters=settings.channel_greeters)  # Replace with actual ping message
        self.assertEqual(len(self.bot.newcomers), 1)

    def test_hello(self):
        botcode.message_response(self.bot, "PRIVMSG sup {}".format(self.bot.nick), "Shauna", ircconn=self.ircsock,
                                 channel=settings.channel, greeters=settings.channel_greeters)
        self.assertTrue(self.ircsock.has_sent_message())
        self.assertIn(self.ircsock.sent_message(), ["PRIVMSG {} :hello Shauna\n".format(settings.channel),
                                                    "PRIVMSG {} :hi Shauna\n".format(settings.channel),
                                                    "PRIVMSG {} :hey Shauna\n".format(settings.channel),
                                                    "PRIVMSG {} :yo Shauna\n".format(settings.channel),
                                                    "PRIVMSG {} :sup Shauna\n".format(settings.channel)])

    def test_help(self):
        botcode.message_response(self.bot, "PRIVMSG info {}".format(self.bot.nick), "Shauna", ircconn=self.ircsock,
                                 channel=settings.channel, greeters=settings.channel_greeters)
        self.assertTrue(self.ircsock.has_sent_message())
        self.assertEqual(self.ircsock.sent_message(),
                         "PRIVMSG {} :I'm a bot!  I'm from here <https://github.com/shaunagm/oh-irc-bot>.  You can change my behavior by submitting a pull request or by talking to shauna.\n".format(
                             settings.channel))

    def test_wait_time_from_admin(self):
        botcode.message_response(self.bot, "{} --wait-time 40".format(self.bot.nick), "shauna", ircconn=self.ircsock,
                                 channel=settings.channel,
                                 greeters=settings.channel_greeters)  # Channel-greeters may also be changed.  :(
        self.assertEqual(self.ircsock.sent_message(),
                         "PRIVMSG {} :shauna the wait time is changing to 40 seconds.\n".format(settings.channel))
        self.assertEqual(self.bot.wait_time, 40)

    def test_wait_time_from_non_admin(self):
        botcode.message_response(self.bot, "{} --wait-time 40".format(self.bot.nick), "Impostor", ircconn=self.ircsock,
                                 channel=settings.channel,
                                 greeters=settings.channel_greeters)  # Channel-greeters may also be changed.  :(
        self.assertEqual(self.ircsock.sent_message(),
                         "PRIVMSG {0} :Impostor you are not authorized to make that change. Please contact one of the channel greeters, like {1}, for assistance.\n".format(
                             settings.channel, botcode.greeter_string(settings.channel_greeters)))
        self.assertEqual(self.bot.wait_time, settings.wait_time)

    def test_pong(self):
        botcode.message_response(self.bot, "PING :", "Shauna", ircconn=self.ircsock, channel=settings.channel,
                                 greeters=settings.channel_greeters)  # Replace this with actual ping message
        self.assertEqual(self.ircsock.sent_message(), "PONG :\n")

    def test_bad_pong(self):
        botcode.message_response(self.bot, "PING!!! :", "Shauna", ircconn=self.ircsock, channel=settings.channel,
                                 greeters=settings.channel_greeters)  # Replace this with actual ping message
        self.assertFalse(self.ircsock.has_sent_message())

    def tearDown(self):
        with open('test_nicks.csv', 'w') as csv_file:
            csv_file.write('Alice\nBob\n')


class TestGreeterString(unittest.TestCase):
    def test_one_greeter(self):
        self.bot = botcode.Bot(None, ['shauna'])
        self.assertEqual(self.bot.greeters_string, "shauna")

    def test_two_greeters(self):
        self.bot = botcode.Bot(None, ['shauna', 'sauna'])
        self.assertEqual(self.bot.greeters_string, "shauna and sauna")

    def test_three_greeters(self):
        self.bot = botcode.Bot(None, ['shauna', 'sauna', 'megafauna'])
        self.assertEqual(self.bot.greeters_string, "shauna, sauna, and megafauna")


# Runs all the unit-tests
if __name__ == '__main__':
    unittest.main()
