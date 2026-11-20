import unittest

from puhis.core.event_log import EventLog


class EventLogTests(unittest.TestCase):
    def test_append_and_list_events_preserves_order_and_bounds(self) -> None:
        log = EventLog(max_entries=3)

        log.append("puhis", "KUUNTELEN!", timestamp="12:00:01")
        log.append("avaa muistio", "Käynnistettiin muistio", timestamp="12:00:02")
        log.append("hei maailma", "Sanelu syötetty", timestamp="12:00:03")
        log.append("puhis seis", "Sanelu pysäytetty", timestamp="12:00:04")

        events = log.list_events()
        self.assertEqual(len(events), 3)
        self.assertEqual([e.timestamp for e in events], ["12:00:02", "12:00:03", "12:00:04"])

    def test_clear_empties_log(self) -> None:
        log = EventLog(max_entries=5)
        log.append("puhis", "KUUNTELEN!")
        log.clear()

        self.assertEqual(log.list_events(), [])

    def test_invalid_max_entries_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            EventLog(max_entries=0)


if __name__ == "__main__":
    unittest.main()
