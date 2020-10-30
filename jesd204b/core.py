from functools import reduce
from operator import and_

from migen import *
from migen.genlib.cdc import MultiReg, ElasticBuffer
from migen.genlib.misc import WaitTimer
from migen.genlib.io import DifferentialInput

from misoc.interconnect.csr import *

from jesd204b.transport import (JESD204BTransportTX,
                                JESD204BSTPLGenerator)
from jesd204b.link import JESD204BLinkTX


class JESD204BCoreTX(Module):
    def __init__(self, phys, jesd_settings, converter_data_width, tx_half=False):
        self.enable = Signal()
        self.jsync = Signal()
        self.jref = Signal()
        self.phy_done = Signal()
        self.ready = Signal()

        self.prbs_config = Signal(4)
        self.stpl_enable = Signal()

        self.sink = Record([("converter"+str(i), converter_data_width)
            for i in range(jesd_settings.nconverters)])

        # # #

        # restart when disabled or on re-synchronization request
        self.jsync_sys = Signal()
        self.specials += MultiReg(self.jsync, self.jsync_sys)
        self.jsync_jesd = Signal()
        self.specials += MultiReg(self.jsync, self.jsync_jesd, "jesd")

        # transport layer
        transport = JESD204BTransportTX(jesd_settings, converter_data_width)
        transport = ClockDomainsRenamer("jesd")(transport)
        self.submodules.transport = transport

        # stpl
        stpl = JESD204BSTPLGenerator(jesd_settings, converter_data_width)
        stpl = ClockDomainsRenamer("jesd")(stpl)
        self.submodules += stpl
        stpl_enable = Signal()
        self.specials += MultiReg(self.stpl_enable, stpl_enable, "jesd")
        self.comb += \
            If(stpl_enable,
                transport.sink.eq(stpl.source)
            ).Else(
                transport.sink.eq(self.sink)
            )

        links = []
        phy_done = Signal()
        self.comb += phy_done.eq(reduce(and_, [phy.transmitter.init.done for phy in phys]))
        for n, (phy, lane) in enumerate(zip(phys, transport.source.flatten())):
            phy_name = "phy{}".format(n)
            phy_cd = phy_name + "_tx"
            phy_half_cd = phy_name + "_tx_half"

            # claim the phy
            setattr(self.submodules, phy_name, phy)

            ebuf = ElasticBuffer(
                len(phy.data) + len(phy.ctrl), 
                4, "jesd", phy_half_cd if tx_half else phy_cd
            )
            setattr(self.submodules, "ebuf{}".format(n), ebuf)

            link = ClockDomainsRenamer("jesd")(
                JESD204BLinkTX(len(phy.data), 
                    jesd_settings, n)
            )
            self.submodules += link
            links.append(link)
            self.comb += [
                link.reset.eq(~phy_done),
                link.jsync.eq(self.jsync_jesd),
                link.jref.eq(self.jref)
            ]

            # connect data
            self.comb += [
                link.sink.data.eq(lane),
                ebuf.din[:len(phy.data)].eq(link.source.data),
                ebuf.din[len(phy.data):].eq(link.source.ctrl),
                phy.data.eq(ebuf.dout[:len(phy.data)]),
                phy.ctrl.eq(ebuf.dout[len(phy.data):])
            ]

            # connect control
            self.comb += phy.transmitter.init.restart.eq(~self.enable)
            self.specials += MultiReg(self.prbs_config,
                                      phy.transmitter.prbs_config,
                                      phy_half_cd if tx_half else phy_cd)
        ready = Signal()
        self.comb += ready.eq(reduce(and_, [link.ready for link in links]))
        self.specials += [
            MultiReg(phy_done, self.phy_done),
            MultiReg(ready, self.ready)
        ]

    # JSYNC is asynchronous and the I/O can be passed directly to the core.
    def register_jsync(self, jsync):
        self.jsync_registered = True
        if isinstance(jsync, Signal):
            self.comb += self.jsync.eq(jsync)
        elif isinstance(jsync, Record):
            self.specials += DifferentialInput(jsync.p, jsync.n, self.jsync)
        else:
            raise ValueError

    # JREF needs to be sampled externally to the core, and needs to be
    # synchronous to the jesd clock domain.
    def register_jref(self, jref):
        self.jref_registered = True
        self.comb += self.jref.eq(jref)

    def do_finalize(self):
        assert hasattr(self, "jsync_registered")
        assert hasattr(self, "jref_registered")


class JESD204BCoreTXControl(Module, AutoCSR):
    def __init__(self, core):
        self.enable = CSRStorage()
        self.phy_done = CSRStatus()
        self.ready = CSRStatus()

        self.prbs_config = CSRStorage(4)
        self.stpl_enable = CSRStorage()

        self.jsync = CSRStatus()

        # # #

        # core control/status
        self.comb += [
            core.enable.eq(self.enable.storage),
            core.prbs_config.eq(self.prbs_config.storage),
            core.stpl_enable.eq(self.stpl_enable.storage),

            self.jsync.status.eq(core.jsync_sys),

            self.phy_done.status.eq(core.phy_done),
            self.ready.status.eq(core.ready)
        ]
