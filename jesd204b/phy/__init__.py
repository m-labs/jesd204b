from migen import *

from jesd204b.common import *
from jesd204b.phy.gtx import GTXTransmitter
from jesd204b.phy.gth import GTHTransmitter


class JESD204BPhyTX(Module):
    def __init__(self, pll, tx_pads, sys_clk_freq, transceiver="gtx"):
        self.data = Signal(32)
        self.ctrl = Signal(32//8)

        # # #

        transmitters = {
            "gtx": GTXTransmitter,
            "gth": GTHTransmitter
        }
        self.submodules.transmitter = transmitters[transceiver](
            pll=pll,
            tx_pads=tx_pads,
            sys_clk_freq=sys_clk_freq
        )
        for i in range(32//8):
            self.comb += [
                self.transmitter.encoder.d[i].eq(self.data[8*i:8*(i+1)]),
                self.transmitter.encoder.k[i].eq(self.ctrl[i])
            ]
