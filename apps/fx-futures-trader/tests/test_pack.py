"""Offline tests for the fx-futures-trader pack: python3 -m unittest discover -s tests -v"""

import contextlib
import datetime as dt
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "fx-core"))

import _synth as SY  # noqa: E402
from fxcore import bars as B, events as E, instruments as I, ledger as L, orders as O  # noqa: E402
from fxcore import plan as P, setups as S, store, tz, execution as X  # noqa: E402


def load_script(rel):
    path = os.path.join(ROOT, rel)
    name = "s_" + rel.replace("/", "_").replace(".py", "")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


scan = load_script("fx-scanner/scan.py")
planc = load_script("fx-entry-exit/plan.py")
replay = load_script("fx-timemachine/replay.py")
size = load_script("fx-risk/size.py")
check = load_script("fx-risk/check.py")
ticket = load_script("fx-broker/ticket.py")
eventsc = load_script("fx-calendar/events.py")

GOLD_DAY = dt.date(2026, 10, 23)          # a Friday
ES_DAY = dt.date(2026, 10, 21)            # a Wednesday


def run(fn, argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            rc = fn(argv)
        except SystemExit as e:
            rc = e.code
    return rc, buf.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="fxt_")
        os.environ["FX_TRADER_DIR"] = os.path.join(self.dir, "trader")
        os.environ["FX_OFFLINE"] = "1"
        self.mt5 = os.path.join(self.dir, "Common")
        self.nt = os.path.join(self.dir, "NT8")
        cfg = json.load(open(os.path.join(ROOT, "fx-risk", "config.example.json")))
        cfg["brokers"]["mt5"]["common_files"] = self.mt5
        cfg["brokers"]["ninjatrader"]["incoming"] = os.path.join(self.nt, "incoming")
        cfg["brokers"]["ninjatrader"]["outgoing"] = os.path.join(self.nt, "outgoing")
        self.cfg = cfg
        self.save_cfg()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)
        os.environ.pop("FX_TRADER_DIR", None)

    def save_cfg(self, **over):
        store.write_json(store.path("config.json"), store.deep_merge(self.cfg, over))

    def gold_bars(self, after=None):
        bars = SY.series("Europe/London", dt.date(2026, 8, 3), 60, "00:00", "21:00", 2600.0, 0.8, seed=3)
        after = after or [(2650, 2652, 2649, 2651.5), (2651.5, 2655, 2651, 2654.2), (2654.2, 2657, 2653.8, 2656.5)]
        bars = SY.shape_day(bars, "Europe/London", GOLD_DAY, "08:00", "08:30", 2650.0, 3.0, after)
        B.save_cache("XAUUSD", 5, bars)
        return bars

    def es_bars(self):
        bars = SY.series("America/New_York", dt.date(2026, 7, 20), 70, "09:30", "16:00", 5800.0, 2.0, seed=11)
        bars = [(t, I.round_tick(o, ES), I.round_tick(h, ES), I.round_tick(l, ES), I.round_tick(c, ES), v) for t, o, h, l, c, v in bars]
        bars = SY.shape_day(bars, "America/New_York", ES_DAY, "09:30", "09:45", 5900.0, 4.0,
                            [(5900, 5906, 5899.5, 5905.5), (5905.5, 5908, 5904, 5907)])
        B.save_cache("ES", 5, bars)
        return bars


ES = I.load_all()["ES"]


class TestTime(unittest.TestCase):
    def test_builtin_zones_match_zoneinfo(self):
        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            self.skipTest("no zoneinfo")
        for zone in ("America/New_York", "America/Chicago", "Europe/London", "Asia/Kolkata", "Asia/Tokyo"):
            zi = ZoneInfo(zone)
            t = dt.datetime(2025, 1, 1, tzinfo=tz.UTC)
            for i in range(0, 2 * 365 * 24, 7):
                u = t + dt.timedelta(hours=i)
                self.assertEqual(tz.to_local(u, zone), u.astimezone(zi).replace(tzinfo=None), (zone, u))

    def test_dst_edges(self):
        # US clocks go back 1 Nov 2026 at 02:00 EDT; London on 25 Oct 2026 at 01:00 UTC
        self.assertEqual(tz.to_local(dt.datetime(2026, 11, 1, 5, 59, tzinfo=tz.UTC), "America/New_York").hour, 1)
        self.assertEqual(tz.to_local(dt.datetime(2026, 11, 1, 6, 0, tzinfo=tz.UTC), "America/New_York").hour, 1)
        self.assertEqual(tz.to_local(dt.datetime(2026, 10, 25, 0, 59, tzinfo=tz.UTC), "Europe/London").hour, 1)
        self.assertEqual(tz.to_local(dt.datetime(2026, 10, 25, 1, 0, tzinfo=tz.UTC), "Europe/London").hour, 1)
        self.assertEqual(tz.to_utc(dt.datetime(2026, 10, 19, 10, 15), "America/New_York"), dt.datetime(2026, 10, 19, 14, 15, tzinfo=tz.UTC))
        self.assertEqual(tz.to_utc(dt.datetime(2026, 10, 19, 10, 15), "Asia/Kolkata"), dt.datetime(2026, 10, 19, 4, 45, tzinfo=tz.UTC))


class TestData(Base):
    def test_mt5_export_ny_plus_7(self):
        txt = "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n" \
              "2026.10.19\t17:15:00\t2650.10\t2651.00\t2649.90\t2650.50\t512\t0\t25\n" \
              "2026.10.19\t17:20:00\t2650.50\t2652.00\t2650.20\t2651.70\t498\t0\t25\n"
        bars = B.parse_csv_text(txt, zone="NY+7")
        # 17:15 server (NY+7, US summer) = 10:15 New York = 14:15 UTC
        self.assertEqual(tz.from_epoch(bars[0][0]), dt.datetime(2026, 10, 19, 14, 15, tzinfo=tz.UTC))
        self.assertEqual(bars[1][4], 2651.70)

    def test_ninjatrader_export_is_bar_end(self):
        txt = "20261019 094000;5900.25;5902;5899.5;5901.75;1200\n20261019 094500;5901.75;5903;5901;5902.5;900\n"
        bars = B.parse_csv_text(txt, zone="America/New_York")
        self.assertEqual(tz.from_epoch(bars[0][0]), dt.datetime(2026, 10, 19, 13, 35, tzinfo=tz.UTC))

    def test_plain_csv_iso(self):
        txt = "time,open,high,low,close,volume\n2026-10-19T14:15:00Z,1.1,1.2,1.0,1.15,5\n"
        bars = B.parse_csv_text(txt)
        self.assertEqual(bars[0][0], int(dt.datetime(2026, 10, 19, 14, 15, tzinfo=tz.UTC).timestamp()))

    def test_yahoo_parse(self):
        doc = {"chart": {"result": [{"timestamp": [100, 400], "indicators": {"quote": [
            {"open": [1, None], "high": [2, 3], "low": [0.5, 1], "close": [1.5, 2], "volume": [10, 20]}]}}]}}
        self.assertEqual(B.parse_yahoo(doc), [(100, 1.0, 2.0, 0.5, 1.5, 10.0)])

    def test_convert(self):
        r = {"USDINR": 88.0, "USDJPY": 150.0}
        self.assertAlmostEqual(store.convert(100, "USD", "INR", r), 8800)
        self.assertAlmostEqual(store.convert(15000, "JPY", "USD", r), 100)
        self.assertAlmostEqual(store.convert(15000, "JPY", "INR", r), 8800)
        with self.assertRaises(KeyError):
            store.convert(1, "CHF", "USD", r)


class TestSetups(Base):
    def test_break_triggers_on_first_close_above(self):
        bars = self.gold_bars()
        spec = I.get("XAUUSD")
        now = tz.epoch(tz.to_utc(dt.datetime(2026, 10, 23, 9, 15), "Europe/London"))
        ev = S.evaluate(bars, spec, "london", setup="break", now=now)
        self.assertEqual(ev["state"], "triggered")
        self.assertEqual(ev["side"], "long")
        self.assertEqual(ev["range_high"], 2653.0)
        self.assertEqual(ev["entry"], 2654.2)
        self.assertEqual(tz.to_local(tz.from_epoch(ev["trigger_close_t"]), "Europe/London").strftime("%H:%M"), "08:40")

    def test_states_through_the_day(self):
        bars = self.gold_bars()
        spec = I.get("XAUUSD")
        at = lambda h, m: tz.epoch(tz.to_utc(dt.datetime(2026, 10, 23, h, m), "Europe/London"))
        self.assertEqual(S.evaluate(bars, spec, "london", now=at(7, 30))["state"], "waiting_for_range")
        self.assertEqual(S.evaluate(bars, spec, "london", now=at(8, 20))["state"], "forming")
        self.assertEqual(S.evaluate(bars, spec, "london", now=at(8, 37))["state"], "waiting")
        self.assertEqual(S.evaluate(bars, spec, "london", now=at(8, 40))["state"], "triggered")

    def test_sweep(self):
        bars = self.gold_bars(after=[(2648, 2649, 2644.5, 2648.6), (2648.6, 2650, 2648, 2649.5)])
        spec = I.get("XAUUSD")
        now = tz.epoch(tz.to_utc(dt.datetime(2026, 10, 23, 9, 0), "Europe/London"))
        ev = S.evaluate(bars, spec, "london", setup="sweep", now=now)
        self.assertEqual((ev["state"], ev["side"], ev["extreme"]), ("triggered", "long", 2644.5))
        br = S.evaluate(bars, spec, "london", setup="break", now=now)
        self.assertNotEqual(br.get("side"), "long")

    def test_es_orb_and_flat_by(self):
        bars = self.es_bars()
        now = tz.epoch(tz.to_utc(dt.datetime(2026, 10, 21, 9, 52), "America/New_York"))
        ev = S.evaluate(bars, ES, "orb", now=now)
        self.assertEqual((ev["state"], ev["side"], ev["entry"]), ("triggered", "long", 5905.5))
        self.assertEqual(tz.to_local(tz.from_epoch(ev["window"]["flat_by"]), "America/New_York").strftime("%H:%M"), "15:55")

    def test_scanner_cli(self):
        self.gold_bars()
        rc, out = run(scan.main, ["--symbols", "XAUUSD", "--offline", "--now", "2026-10-23 13:12", "--write"])
        self.assertEqual(rc, 0)
        self.assertIn("triggered", out)
        self.assertIn("LONG at 08:40 LDN (13:10 IST)", out)
        rc, out = run(scan.main, ["list"])
        self.assertIn("MCX_GOLD", out)
        self.assertIn("signals only", out)


class TestPlanAndWalk(Base):
    def test_plan_targets_and_rounding(self):
        self.gold_bars()
        rc, out = run(planc.main, ["make", "XAUUSD", "--offline", "--now", "2026-10-23 13:12", "--write"])
        self.assertEqual(rc, 0, out)
        pl = store.read_json(store.path("plan.json"))
        self.assertEqual((pl["entry"], pl["stop"]), (2654.2, 2650.0))
        self.assertEqual([t["price"] for t in pl["targets"]], [2658.4, 2662.6, 2666.8])
        self.assertAlmostEqual(pl["rr"], 2.0, places=2)

    def test_stop_methods(self):
        ev = {"state": "triggered", "side": "short", "entry": 5895.0, "range_mid": 5900.0, "range_high": 5904.0,
              "range_low": 5896.0, "extreme": 5904.5, "bar_atr": 3.1, "setup": "break", "range": "orb", "day": "x",
              "trigger_close_t": 0, "window": {"until": 0, "flat_by": None, "horizon": 0}}
        self.assertEqual(P.stop_price(ev, ES, "range_mid"), 5900.0)
        self.assertEqual(P.stop_price(ev, ES, "range_far"), 5904.0)
        self.assertEqual(P.stop_price(ev, ES, "extreme:2"), 5905.0)
        self.assertEqual(P.stop_price(ev, ES, "atr:1"), 5898.25)   # 5898.1 rounded up to the tick
        with self.assertRaises(ValueError):
            P.build(dict(ev, entry=5905.0), ES, stop="range_mid")

    def test_walk(self):
        tps = [{"r": 1, "price": 101, "weight": 1 / 3}, {"r": 2, "price": 102, "weight": 1 / 3}, {"r": 3, "price": 103, "weight": 1 / 3}]
        self.assertEqual(P.walk([(100, 100.5, 98.9, 99)], "long", 100, 99, tps)["outcome"], "stop")
        both = P.walk([(100, 101.5, 98.5, 100)], "long", 100, 99, tps)
        self.assertEqual((both["outcome"], both["r"]), ("stop", -1.0))      # stop wins inside one bar
        be = P.walk([(100, 101.2, 99.9, 101), (101, 101.5, 99.8, 100)], "long", 100, 99, tps)
        self.assertEqual(be["outcome"], "tp1")
        self.assertAlmostEqual(be["r"], 1 / 3, places=3)                    # rest out at breakeven
        allt = P.walk([(100, 103.5, 99.5, 103)], "long", 100, 99, tps)
        self.assertAlmostEqual(allt["r"], 2.0, places=3)
        gap = P.walk([(97, 98, 96, 97.5)], "long", 100, 99, tps)
        self.assertAlmostEqual(gap["r"], -3.0, places=3)                    # gapped through the stop

    def test_manual_plan(self):
        rc, out = run(planc.main, ["manual", "XAUUSD", "--side", "short", "--entry", "2650.2", "--stop", "2655.2",
                                   "--now", "2026-10-21 14:00", "--write"])
        self.assertEqual(rc, 0, out)
        pl = store.read_json(store.path("plan.json"))
        self.assertEqual([t["price"] for t in pl["targets"]], [2645.2, 2640.2, 2635.2])


class TestReplay(Base):
    def test_seeded_and_reasonable(self):
        self.gold_bars()
        run(planc.main, ["make", "XAUUSD", "--offline", "--now", "2026-10-23 13:12", "--write"])
        rc, out1 = run(replay.main, ["run", "--runs", "2000", "--seed", "19", "--offline", "--write"])
        self.assertEqual(rc, 0, out1)
        r1 = store.read_json(store.path("replay.json"))
        rc, out2 = run(replay.main, ["run", "--runs", "2000", "--seed", "19", "--offline"])
        self.assertEqual(out1.split("wrote")[0], out2)
        mc = r1["monte_carlo"]
        self.assertAlmostEqual(sum(mc["outcomes"].values()), 1.0, places=3)
        self.assertGreaterEqual(mc["reached_target"][0], mc["reached_target"][1])
        self.assertGreater(r1["history"]["fired"], 20)
        self.assertIn("coin flip", r1["verdict"])


def _plan_gold(self):
    self.gold_bars()
    run(planc.main, ["make", "XAUUSD", "--offline", "--now", "2026-10-23 13:12", "--write"])


class TestSizing(Base):
    def test_gold_lots_usd(self):
        _plan_gold(self)
        o = size.size(store.read_json(store.path("plan.json")), I.get("XAUUSD"), store.load_config())
        # $10,000 x 0.5% = $50; 4.20 stop = 420 ticks x $1 = $420 per lot -> 0.11 lot
        self.assertEqual(o["qty"], 0.11)
        self.assertEqual([l["qty"] for l in o["legs"]], [0.04, 0.04, 0.03])
        self.assertAlmostEqual(o["max_loss"], 46.2, places=2)
        self.assertAlmostEqual(o["margin_est"], 0.11 * 100 * 2654.2 / 20, places=1)

    def test_inr_account_mcx_and_usd_products(self):
        cfg = store.deep_merge(store.load_config(), {"account": {"ccy": "INR", "balance": 500000, "risk_per_trade_pct": 0.5}})
        pl = {"entry": 74250.0, "stop": 74150.0, "side": "long", "risk_ticks": 100, "risk": 100.0,
              "targets": [{"r": 1, "price": 74350.0, "weight": 0.5}, {"r": 2, "price": 74450.0, "weight": 0.5}],
              "rule": {"setup": "break"}, "be_after_tp1": True, "signal_t": "2026-10-21T04:00:00Z",
              "valid_until": "2026-10-21T05:30:00Z", "flat_by": None}
        o = size.size(pl, I.get("MCX_GOLDM"), cfg, broker="signals")
        # Rs 2,500 risk; 100 ticks x Rs 10 = Rs 1,000 per lot -> 2 lots
        self.assertEqual((o["qty"], o["max_loss"]), (2, 2000.0))
        es = dict(pl, entry=5905.5, stop=5900.0, targets=[{"r": 1, "price": 5911.0, "weight": 1.0}])
        o2 = size.size(es, I.get("MES"), cfg, broker="signals")
        # 22 ticks x $1.25 = $27.5 = Rs 2,420 per contract -> 1
        self.assertEqual(o2["qty"], 1)
        self.assertAlmostEqual(o2["max_loss"], 2420.0, places=2)

    def test_refuses_when_minimum_too_big_or_rate_missing(self):
        cfg = store.load_config()
        pl = {"entry": 5905.5, "stop": 5880.0, "side": "long", "risk_ticks": 102, "risk": 25.5,
              "targets": [{"r": 1, "price": 5931.0, "weight": 1.0}], "rule": {"setup": "break"}, "be_after_tp1": True,
              "signal_t": "x", "valid_until": "x"}
        with self.assertRaises(ValueError) as e:
            size.size(pl, I.get("ES"), cfg, broker="signals")
        self.assertIn("micro", str(e.exception))
        cfg2 = store.deep_merge(cfg, {"rates": {"USDJPY": None}})
        cfg2["rates"] = {}
        jp = dict(pl, entry=152.0, stop=151.8, targets=[{"r": 1, "price": 152.2, "weight": 1.0}])
        with self.assertRaises(KeyError):
            size.size(jp, I.get("USDJPY"), cfg2, broker="signals")

    def test_one_contract_drops_extra_targets(self):
        cfg = store.deep_merge(store.load_config(), {"account": {"risk_per_trade_money": 40}})
        pl = {"entry": 5905.5, "stop": 5900.0, "side": "long", "risk_ticks": 22, "risk": 5.5,
              "targets": [{"r": 1, "price": 5911.0, "weight": 0.34}, {"r": 2, "price": 5916.5, "weight": 0.33},
                          {"r": 3, "price": 5922.0, "weight": 0.33}],
              "rule": {"setup": "break"}, "be_after_tp1": True, "signal_t": "x", "valid_until": "x"}
        o = size.size(pl, I.get("MES"), cfg, broker="signals")
        self.assertEqual(o["qty"], 1)
        self.assertEqual(len(o["legs"]), 1)
        self.assertIn("dropped", o["note"])


class TestRiskGate(Base):
    def _order(self, **cfg_over):
        _plan_gold(self)
        self.save_cfg(**cfg_over)
        return run(size.main, ["--write", "--now", "2026-10-23 13:13"])

    def test_verify_spec_blocks_then_acknowledge_passes(self):
        self._order(broker="mt5")
        rc, out = run(check.main, ["--now", "2026-10-23 13:14"])
        self.assertEqual(rc, 2)
        self.assertIn("marked VERIFY", out)
        self.save_cfg(broker="mt5", limits={"acknowledge_specs": ["XAUUSD"]})
        rc, out = run(check.main, ["--now", "2026-10-23 13:14"])
        self.assertEqual(rc, 0, out)
        self.assertIn("PASS", out)

    def test_blocks(self):
        self._order(limits={"acknowledge_specs": ["XAUUSD"], "min_rr": 2.5, "max_risk_money": 30})
        rc, out = run(check.main, ["--now", "2026-10-23 13:35", "--price", "2656.0"])
        self.assertEqual(rc, 2)
        self.assertIn("under your minimum", out)
        self.assertIn("over your per-trade limit", out)
        self.assertIn("minutes old", out)
        self.assertIn("moved 0.43R", out)

    def test_news_blackout(self):
        self._order(limits={"acknowledge_specs": ["XAUUSD"]})
        E.save([{"title": "Core PCE", "country": "USD", "t": "2026-10-23T07:50:00Z", "impact": "High"}])
        rc, out = run(check.main, ["--now", "2026-10-23 13:14"])
        self.assertIn("news blackout: USD High Core PCE", out)

    def test_weekend_cutoff(self):
        _plan_gold(self)
        pl = store.read_json(store.path("plan.json"))
        pl["signal_t"] = "2026-10-23T19:40:00Z"
        pl["valid_until"] = "2026-10-23T23:00:00Z"
        store.write_json(store.path("plan.json"), pl)
        self.save_cfg(limits={"acknowledge_specs": ["XAUUSD"]})
        run(size.main, ["--write", "--now", "2026-10-24 01:15"])
        rc, out = run(check.main, ["--now", "2026-10-24 01:15"])   # 15:45 NY Friday
        self.assertIn("weekend", out)

    def test_paper_mode_needs_sim_account(self):
        self.es_bars()
        run(planc.main, ["make", "ES", "--offline", "--now", "2026-10-21 19:22", "--write"])
        self.save_cfg(broker="ninjatrader", brokers={"ninjatrader": {"account": "Live1234"}},
                      account={"risk_per_trade_money": 300}, limits={"min_rr": 1.0})
        run(size.main, ["--write", "--now", "2026-10-21 19:22"])
        rc, out = run(check.main, ["--now", "2026-10-21 19:23"])
        self.assertIn("not a Sim account", out)

    def test_daily_limit_and_trade_count(self):
        self._order(limits={"acknowledge_specs": ["XAUUSD"], "max_trades_per_day": 1})
        now = store.parse_iso("2026-10-23T09:00:00Z")
        L.append({"kind": "sent", "order_id": "TOLD", "symbol": "EURUSD", "side": "long", "qty": 0.1, "max_loss": 50, "order_kind": "open"}, now)
        L.append({"kind": "placed", "order_id": "TOLD", "symbol": "EURUSD", "filled_qty": 0.1, "filled_price": 1.08}, now)
        L.append({"kind": "closed", "order_id": "TOLD", "symbol": "EURUSD", "qty": 0.1, "pnl": -180}, now)
        rc, out = run(check.main, ["--now", "2026-10-23 13:14"])
        self.assertIn("daily loss limit", out)
        self.assertIn("already 1 trades today", out)


class TestBroker(Base):
    def _ready(self, broker="mt5", **over):
        _plan_gold(self)
        self.save_cfg(broker=broker, limits={"acknowledge_specs": ["XAUUSD"]}, **over)
        run(size.main, ["--write", "--now", "2026-10-23 13:13"])
        rc, out = run(check.main, ["--now", "2026-10-23 13:14"])
        self.assertEqual(rc, 0, out)
        return O.load()["orders"][0]

    def test_yes_rules(self):
        o = self._ready()
        specs = I.load_all()
        ok = lambda r: ticket.is_explicit_yes(r, o, 1, specs)[0]
        self.assertTrue(ok("yes"))
        self.assertTrue(ok("Yes."))
        self.assertTrue(ok("yes, place ticket 1"))
        self.assertTrue(ok("yes buy 0.11 xauusd"))
        self.assertFalse(ok("sure"))
        self.assertFalse(ok("yes to all"))
        self.assertFalse(ok("yes but wait"))
        self.assertFalse(ok("yes eurusd"))
        self.assertFalse(ok("yes 0.5 lots"))

    def test_send_needs_yes_then_writes_mt5_ticket(self):
        o = self._ready()
        rc, out = run(ticket.main, ["send", "--index", "1", "--now", "2026-10-23 13:15"])
        self.assertEqual(rc, 2)
        self.assertIn("no recorded yes", out)
        rc, out = run(ticket.main, ["approve", "--index", "1", "--reply", "ok", "--now", "2026-10-23 13:15"])
        self.assertIn("Not recorded", out)
        rc, out = run(ticket.main, ["approve", "--index", "1", "--reply", "yes", "--now", "2026-10-23 13:15"])
        self.assertIn("Recorded your yes", out)
        rc, out = run(ticket.main, ["send", "--index", "1", "--now", "2026-10-23 13:16"])
        self.assertEqual(rc, 0, out)
        pend = os.path.join(self.mt5, "RajeshHub", "tickets", "pending")
        files = os.listdir(pend)
        self.assertEqual(len(files), 1)
        raw = open(os.path.join(pend, files[0])).read()
        d = json.loads(raw)
        self.assertEqual((d["action"], d["dir"], d["symbol"], d["legs_total"]), ("OPEN", "BUY", "XAUUSD", 3))
        self.assertEqual((d["leg1_qty"], d["leg3_qty"], d["stop"], d["require_demo"]), (0.04, 0.03, 2650.0, 1))
        self.assertNotIn("{\"", raw[1:])            # flat: no nested objects
        self.assertEqual(d["expires_utc"] - d["created_utc"], 120)
        rc, out = run(ticket.main, ["send", "--index", "1", "--now", "2026-10-23 13:16"])
        self.assertIn("ALREADY SENT", out)

    def test_approval_expires(self):
        self._ready()
        run(ticket.main, ["approve", "--index", "1", "--reply", "yes", "--now", "2026-10-23 13:15"])
        rc, out = run(ticket.main, ["send", "--index", "1", "--now", "2026-10-23 13:27"])
        self.assertEqual(rc, 2)

    def test_mt5_sync_from_ea_results(self):
        o = self._ready()
        run(ticket.main, ["approve", "--index", "1", "--reply", "yes", "--now", "2026-10-23 13:15"])
        run(ticket.main, ["send", "--index", "1", "--now", "2026-10-23 13:16"])
        res = os.path.join(self.mt5, "RajeshHub", "tickets", "results")
        os.makedirs(res)
        write = lambda d: open(os.path.join(res, o["id"] + ".json"), "w").write(json.dumps(d))
        write({"ticket_id": o["id"], "status": "placed", "filled_qty": 0.11, "avg_price": 2654.4, "positions": "1,2,3", "closed_qty": 0, "pnl": 0})
        run(ticket.main, ["sync"])
        write({"ticket_id": o["id"], "status": "placed", "filled_qty": 0.11, "avg_price": 2654.4, "closed_qty": 0.04, "pnl": 16.0})
        run(ticket.main, ["sync"])
        run(ticket.main, ["sync"])                   # same totals: nothing new
        write({"ticket_id": o["id"], "status": "placed", "filled_qty": 0.11, "avg_price": 2654.4, "closed_qty": 0.11, "pnl": 16.0})
        run(ticket.main, ["sync"])
        p = L.positions()[o["id"]]
        self.assertEqual((p["status"], round(p["pnl"], 2), p["qty_open"]), ("closed", 16.0, 0.0))

    def test_ninjatrader_protect_flow(self):
        self.es_bars()
        run(planc.main, ["make", "ES", "--offline", "--now", "2026-10-21 19:22", "--write"])
        self.save_cfg(broker="ninjatrader", account={"risk_per_trade_money": 900},
                      limits={"min_rr": 1.0, "max_risk_pct": 10, "daily_loss_limit_pct": 20})
        run(size.main, ["--write", "--now", "2026-10-21 19:22"])
        rc, out = run(check.main, ["--now", "2026-10-21 19:23"])
        self.assertEqual(rc, 0, out)
        o = O.load()["orders"][0]
        self.assertEqual((o["broker_symbol"], o["qty"]), ("ES 12-26", 3))
        run(ticket.main, ["approve", "--index", "1", "--reply", "yes", "--now", "2026-10-21 19:24"])
        rc, out = run(ticket.main, ["send", "--index", "1", "--now", "2026-10-21 19:24", "--wait", "1"])
        self.assertEqual(rc, 0, out)
        inc = os.path.join(self.nt, "incoming")
        entry = open(os.path.join(inc, sorted(os.listdir(inc))[0])).read().strip()
        self.assertEqual(entry, "PLACE;Sim101;ES 12-26;BUY;3;MARKET;0;0;DAY;;%sE;;" % o["id"])
        self.assertEqual(entry.count(";"), 12)
        outg = os.path.join(self.nt, "outgoing")
        os.makedirs(outg)
        open(os.path.join(outg, o["id"] + "E.txt"), "w").write("FILLED;3;5905.75")
        run(ticket.main, ["sync"])
        prot = [f for f in os.listdir(inc) if f.endswith(o["id"] + "P.txt")]
        self.assertEqual(len(prot), 1)
        lines = open(os.path.join(inc, prot[0])).read().splitlines()
        self.assertEqual(len(lines), 6)
        self.assertIn("PLACE;Sim101;ES 12-26;SELL;1;STOPMARKET;0;5900;DAY;%sO1;%sS1;;" % (o["id"], o["id"]), lines)
        open(os.path.join(outg, o["id"] + "P1.txt"), "w").write("FILLED;1;5911")
        run(ticket.main, ["sync"])
        be = [f for f in os.listdir(inc) if f.endswith(o["id"] + "B.txt")]
        self.assertEqual(len(be), 1)
        self.assertIn("CHANGE;;;;1;;0;5905.75;;;%sS2;;" % o["id"], open(os.path.join(inc, be[0])).read())
        p = L.positions()[o["id"]]
        self.assertEqual(p["qty_open"], 2.0)
        self.assertAlmostEqual(p["pnl"], 262.5)          # 21 ticks x $12.50
        # flatten -> close ticket -> risk -> yes -> send
        run(ticket.main, ["flatten", "--order", o["id"], "--now", "2026-10-21 19:40"])
        rc, out = run(check.main, ["--now", "2026-10-21 19:40"])
        self.assertEqual(rc, 0, out)
        run(ticket.main, ["approve", "--index", "1", "--reply", "yes", "--now", "2026-10-21 19:41"])
        rc, out = run(ticket.main, ["send", "--index", "1", "--now", "2026-10-21 19:41"])
        self.assertEqual(rc, 0, out)
        close = [f for f in os.listdir(inc) if "oif" in f and f.endswith(".txt")]
        body = "".join(open(os.path.join(inc, f)).read() for f in close)
        self.assertIn("CLOSEPOSITION;Sim101;ES 12-26;;;;;;;;;;", body)
        close_id = O.load()["orders"][0]["id"]
        self.assertEqual(L.positions()[close_id]["kind"], "close")
        open(os.path.join(outg, "ES 12-26 Globex_Sim101_Position.txt"), "w").write("FLAT;0;0")
        run(ticket.main, ["sync"])
        self.assertEqual(L.positions()[o["id"]]["status"], "closed")
        run(ticket.main, ["close", "--order", o["id"], "--pnl", "-40"])
        self.assertAlmostEqual(L.positions()[o["id"]]["pnl"], 222.5)
        # a new ES trade is no longer blocked by "already have an open ES trade"
        self.assertFalse([p for p in L.positions().values() if p["symbol"] == "ES" and p["status"] in ("sent", "open") and p["kind"] == "open"])

    def test_signals_mode_manual_fill_and_close(self):
        o = self._ready(broker="signals")
        run(ticket.main, ["approve", "--index", "1", "--reply", "yes", "--now", "2026-10-23 13:15"])
        rc, out = run(ticket.main, ["send", "--index", "1", "--now", "2026-10-23 13:15"])
        self.assertIn("place this yourself", out)
        run(ticket.main, ["fill", "--order", o["id"], "--qty", "0.11", "--price", "2654.2"])
        run(ticket.main, ["close", "--order", o["id"], "--price", "2650.0"])
        p = L.positions()[o["id"]]
        self.assertEqual(p["status"], "closed")
        self.assertAlmostEqual(p["pnl"], -46.2, places=2)


class TestCalendar(Base):
    def test_feed_and_manual(self):
        evs = E.parse_feed([{"title": "Non-Farm Employment Change", "country": "USD", "date": "2026-11-06T08:30:00-05:00",
                             "impact": "High", "forecast": "", "previous": ""}])
        self.assertEqual(evs[0]["t"], "2026-11-06T13:30:00Z")
        E.save(evs)
        run(eventsc.main, ["add", "--title", "RBI policy", "--country", "INR", "--at", "2026-12-05 10:00"])
        cfg = store.load_config()
        gold, nifty = I.get("XAUUSD"), I.get("NIFTY")
        self.assertFalse(E.blackout(gold, store.parse_iso("2026-11-06T13:20:00Z"), cfg)[0])
        self.assertTrue(E.blackout(gold, store.parse_iso("2026-11-06T13:50:00Z"), cfg)[0])
        self.assertFalse(E.blackout(nifty, store.parse_iso("2026-12-05T04:35:00Z"), cfg)[0])
        self.assertTrue(E.blackout(gold, store.parse_iso("2026-12-05T04:35:00Z"), cfg)[0])


class TestRepo(unittest.TestCase):
    def test_every_skill_has_frontmatter_and_its_script(self):
        for d in sorted(os.listdir(ROOT)):
            if d.startswith("fx-") and d != "fx-core":
                md = open(os.path.join(ROOT, d, "SKILL.md")).read()
                self.assertTrue(md.startswith("---\nname: %s\n" % d), d)
                for line in md.splitlines():
                    if "${CLAUDE_SKILL_DIR}/" in line:
                        script = line.split("${CLAUDE_SKILL_DIR}/")[1].split('"')[0]
                        self.assertTrue(os.path.exists(os.path.join(ROOT, d, script)), (d, script))

    def test_specs_resolve(self):
        specs = I.load_all()
        for k, s in specs.items():
            for f in ("tick_size", "tick_value", "min_qty", "qty_step", "max_qty", "class", "ranges"):
                self.assertIn(f, s, (k, f))
            self.assertIn(s.get("default_range"), s["ranges"], k)


if __name__ == "__main__":
    unittest.main()
