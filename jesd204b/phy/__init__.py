from migen import *

from jesd204b.common import *
from jesd204b.phy.gtx import GTXTransmitter
from jesd204b.phy.gth import GTHTransmitter

from misoc.interconnect.csr import *


class JESD204BPhyTX(Module, AutoCSR):
    def __init__(self, pll, refclk, tx_pads, sys_clk_freq, tx_half=False, transceiver="gtx"):
        self.data = Signal(64 if tx_half else 32)
        self.ctrl = Signal((64 if tx_half else 32)//8)

        # # #

        transmitters = {
            "gtx": GTXTransmitter,
            "gth": GTHTransmitter
        }
        self.submodules.transmitter = transmitters[transceiver](
            pll=pll,
            refclk=refclk,
            tx_pads=tx_pads,
            sys_clk_freq=sys_clk_freq,
            tx_half=tx_half
        )
        for i in range((64 if tx_half else 32)//8):
            self.comb += [
                self.transmitter.encoder.d[i].eq(self.data[8*i:8*(i+1)]),
                self.transmitter.encoder.k[i].eq(self.ctrl[i])
            ]
