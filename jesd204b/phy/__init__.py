from migen import *

from jesd204b.common import *
from jesd204b.phy.gtx import GTXTransmitter


class JESD204BPhyTX(Module):
    def __init__(self, pll, tx_pads, sys_clk_freq):
        self.data = Signal(32)
        self.ctrl = Signal(32//8)

        # # #

        # transceiver
        self.submodules.gtx = GTXTransmitter(
                pll=pll,
                tx_pads=tx_pads,
                sys_clk_freq=sys_clk_freq)

        for i in range(32//8):
            self.comb += [
                self.gtx.encoder.d[i].eq(self.data[8*i:8*(i+1)]),
                self.gtx.encoder.k[i].eq(self.ctrl[i])
            ]
