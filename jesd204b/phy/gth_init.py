from math import ceil

from migen import *
from migen.genlib.cdc import MultiReg
from migen.genlib.misc import WaitTimer


class GTHInit(Module):
    def __init__(self, sys_clk_freq, rx):
        self.done = Signal()
        self.restart = Signal()

        # GTH signals
        self.plllock = Signal()
        self.pllreset = Signal()
        self.gtXxreset = Signal()
        self.Xxresetdone = Signal()
        self.Xxdlysreset = Signal()
        self.Xxdlysresetdone = Signal()
        self.Xxphaligndone = Signal()

        # # #

        # Double-latch transceiver asynch outputs
        plllock = Signal()
        Xxresetdone = Signal()
        Xxdlysresetdone = Signal()
        Xxphaligndone = Signal()
        self.specials += [
            MultiReg(self.plllock, plllock),
            MultiReg(self.Xxresetdone, Xxresetdone),
            MultiReg(self.Xxdlysresetdone, Xxdlysresetdone),
            MultiReg(self.Xxphaligndone, Xxphaligndone)
        ]

        # Deglitch FSM outputs driving transceiver asynch inputs
        gtXxreset = Signal()
        Xxdlysreset = Signal()
        self.sync += [
            self.gtXxreset.eq(gtXxreset),
            self.Xxdlysreset.eq(Xxdlysreset),
        ]

        # PLL reset must be at least 2us
        pll_reset_cycles = ceil(2000*sys_clk_freq/1000000000)
        pll_reset_timer = WaitTimer(pll_reset_cycles)
        self.submodules += pll_reset_timer

        startup_fsm = ResetInserter()(FSM(reset_state="RESET_ALL"))
        self.submodules += startup_fsm

        ready_timer = WaitTimer(1*sys_clk_freq//1000)
        self.submodules += ready_timer
        self.comb += [
            ready_timer.wait.eq(~self.done & ~startup_fsm.reset),
            startup_fsm.reset.eq(self.restart | ready_timer.done)
        ]

        if rx:
            cdr_stable_timer = WaitTimer(1024)
            self.submodules += cdr_stable_timer

        Xxphaligndone_r = Signal(reset=1)
        Xxphaligndone_rising = Signal()
        self.sync += Xxphaligndone_r.eq(Xxphaligndone)
        self.comb += Xxphaligndone_rising.eq(Xxphaligndone & ~Xxphaligndone_r)

        startup_fsm.act("RESET_ALL",
            gtXxreset.eq(1),
            self.pllreset.eq(1),
            pll_reset_timer.wait.eq(1),
            If(pll_reset_timer.done,
                NextState("RELEASE_PLL_RESET")
            )
        )
        startup_fsm.act("RELEASE_PLL_RESET",
            gtXxreset.eq(1),
            If(plllock, NextState("RELEASE_GTH_RESET"))
        )
        # Release GTH reset and wait for GTH resetdone
        # (from UG476, GTH is reset on falling edge
        # of gtXxreset)
        if rx:
            startup_fsm.act("RELEASE_GTH_RESET",
                cdr_stable_timer.wait.eq(1),
                If(Xxresetdone & cdr_stable_timer.done, NextState("ALIGN"))
            )
        else:
            startup_fsm.act("RELEASE_GTH_RESET",
                If(Xxresetdone, NextState("ALIGN"))
            )
        # Start delay alignment (pulse)
        startup_fsm.act("ALIGN",
            Xxdlysreset.eq(1),
            NextState("WAIT_ALIGN")
        )
        # Wait for delay alignment
        startup_fsm.act("WAIT_ALIGN",
            If(Xxdlysresetdone,
                NextState("WAIT_FIRST_ALIGN_DONE")
            )
        )
        # Wait 2 rising edges of Xxphaligndone
        # (from UG576 in TX Buffer Bypass in Single-Lane Auto Mode)
        startup_fsm.act("WAIT_FIRST_ALIGN_DONE",
            If(Xxphaligndone_rising, NextState("WAIT_SECOND_ALIGN_DONE"))
        )
        startup_fsm.act("WAIT_SECOND_ALIGN_DONE",
            If(Xxphaligndone_rising, NextState("READY"))
        )
        startup_fsm.act("READY",
            self.done.eq(1)
        )
