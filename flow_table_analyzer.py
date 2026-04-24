"""
flow_table_analyzer.py
Multi-Switch Flow Table Analyzer – SDN Mininet Project (Task 8)

Features:
  - Handles packet_in events and installs match+action flow rules
  - Retrieves flow entries from all switches via OFPFlowStatsRequest
  - Displays rule details (match, actions, priority, timeouts)
  - Identifies active vs unused (zero-packet-count) rules
  - Updates dynamically on a polling interval
"""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types
from ryu.lib import hub
import datetime

POLL_INTERVAL = 10  # seconds between flow table polls


class FlowTableAnalyzer(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(FlowTableAnalyzer, self).__init__(*args, **kwargs)
        # mac_to_port[dpid][mac] = port
        self.mac_to_port = {}
        # flow_stats[dpid] = list of flow stat entries
        self.flow_stats = {}
        # Start background polling thread
        self.datapaths = {}
        self.monitor_thread = hub.spawn(self._monitor)

    # ------------------------------------------------------------------ #
    #  Switch handshake – install table-miss entry                         #
    # ------------------------------------------------------------------ #
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        self.datapaths[datapath.id] = datapath
        self.logger.info("[SWITCH] Connected: dpid=%016x", datapath.id)

        # Table-miss: send to controller, lowest priority
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self._add_flow(datapath, priority=0, match=match, actions=actions,
                       idle_timeout=0, hard_timeout=0)

    # ------------------------------------------------------------------ #
    #  Packet-in handler – learning switch + flow installation             #
    # ------------------------------------------------------------------ #
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        # Ignore LLDP
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst = eth.dst
        src = eth.src
        dpid = datapath.id

        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port
        self.logger.info("[PKT_IN] dpid=%016x src=%s dst=%s in_port=%s",
                         dpid, src, dst, in_port)

        # Decide output port
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # Install flow rule (not for flood)
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            self._add_flow(datapath, priority=1, match=match, actions=actions,
                           idle_timeout=30, hard_timeout=120)
            self.logger.info("[FLOW_INSTALL] dpid=%016x %s -> port %s",
                             dpid, dst, out_port)

        # Send packet out
        data = msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None
        out = parser.OFPPacketOut(datapath=datapath,
                                  buffer_id=msg.buffer_id,
                                  in_port=in_port,
                                  actions=actions,
                                  data=data)
        datapath.send_msg(out)

    # ------------------------------------------------------------------ #
    #  Helper – add a flow rule                                            #
    # ------------------------------------------------------------------ #
    def _add_flow(self, datapath, priority, match, actions,
                  idle_timeout=0, hard_timeout=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        mod = parser.OFPFlowMod(datapath=datapath,
                                 priority=priority,
                                 idle_timeout=idle_timeout,
                                 hard_timeout=hard_timeout,
                                 match=match,
                                 instructions=inst)
        datapath.send_msg(mod)

    # ------------------------------------------------------------------ #
    #  Background monitor – polls all switches every POLL_INTERVAL sec     #
    # ------------------------------------------------------------------ #
    def _monitor(self):
        while True:
            hub.sleep(POLL_INTERVAL)
            for dp in list(self.datapaths.values()):
                self._request_flow_stats(dp)

    def _request_flow_stats(self, datapath):
        parser = datapath.ofproto_parser
        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    # ------------------------------------------------------------------ #
    #  Flow stats reply handler – display + classify rules                 #
    # ------------------------------------------------------------------ #
    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        dpid = ev.msg.datapath.id
        body = ev.msg.body
        self.flow_stats[dpid] = body

        now = datetime.datetime.now().strftime("%H:%M:%S")
        print("\n" + "=" * 70)
        print(f"  FLOW TABLE SNAPSHOT  |  Switch dpid={dpid:016x}  |  {now}")
        print("=" * 70)
        print(f"  {'Priority':>8}  {'TableID':>7}  {'IdleTO':>6}  "
              f"{'HardTO':>6}  {'Packets':>8}  {'Bytes':>10}  Status    Match")
        print("-" * 70)

        active = 0
        unused = 0

        for stat in sorted(body, key=lambda s: s.priority, reverse=True):
            pkt_cnt = stat.packet_count
            status = "ACTIVE" if pkt_cnt > 0 else "UNUSED"
            if pkt_cnt > 0:
                active += 1
            else:
                unused += 1

            match_str = str(stat.match).replace("OFPMatch", "").strip("()")
            print(f"  {stat.priority:>8}  {stat.table_id:>7}  "
                  f"{stat.idle_timeout:>6}  {stat.hard_timeout:>6}  "
                  f"{pkt_cnt:>8}  {stat.byte_count:>10}  {status:<8}  "
                  f"{match_str[:40]}")

        print("-" * 70)
        print(f"  Total: {len(body)} rules  |  Active: {active}  |  Unused: {unused}")
        print("=" * 70 + "\n")
