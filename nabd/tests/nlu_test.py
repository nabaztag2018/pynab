import unittest
import asyncio
import datetime
import sys
from nabd.nlu import NLU


class TestNLU(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def interpret(self, nlu, str):
        task = self.loop.create_task(nlu.interpret(str))
        self.loop.run_until_complete(task)
        return task.result()

    def test_en(self):
        nlu = NLU('en_US')
        result = self.interpret(nlu, "i'm trying to think but nothing happens")
        if result != None:
            self.assertEqual(result['intent'], 'surprise')
        else:
            self.assertEqual(result, None)

        result = self.interpret(nlu, "what's the weather like today")
        self.assertEqual(result['intent'], 'weather_forecast')
        today = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d 00:00:00 +00:00')
        self.assertEqual(result['date'], today)

        result = self.interpret(nlu, "tell me a joke")
        self.assertEqual(result['intent'], 'surprise')

        result = self.interpret(nlu, "make me laugh")
        self.assertEqual(result['intent'], 'surprise')

        result = self.interpret(nlu, "should i go outside today")
        self.assertEqual(result['intent'], 'airquality_forecast')
        today = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d 00:00:00 +00:00')
        self.assertEqual(result['date'], today)

    def test_fr(self):
        nlu = NLU('fr_FR')
        result = self.interpret(nlu, "blablabla")
        self.assertEqual(result, None)

        result = self.interpret(nlu, u"météo")
        self.assertEqual(result['intent'], 'weather_forecast')
        self.assertNotIn('date', result)

        result = self.interpret(nlu, "est-ce qu'il va pleuvoir aujourd'hui")
        self.assertEqual(result['intent'], 'weather_forecast')
        today = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d 00:00:00 +00:00')
        self.assertEqual(result['date'], today)

        result = self.interpret(nlu, "guili guili")
        self.assertEqual(result['intent'], 'surprise')

        result = self.interpret(nlu, "fais-moi rire")
        self.assertEqual(result['intent'], 'surprise')

        result = self.interpret(nlu, u"c'est pas un peu pollué aujourd'hui")
        self.assertEqual(result['intent'], 'airquality_forecast')
        today = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d 00:00:00 +00:00')
        self.assertEqual(result['date'], today)
