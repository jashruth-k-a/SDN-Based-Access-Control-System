"""
SDN Access Control System - Ryu Controller
Whitelist: only h1<->h2 are authorized to communicate
All other pairs are blocked
"""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet

class AccessControlController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(AccessControlController, self).__init__(*args, **kwargs)

        # MAC address table for learning
        self.mac_to_port = {}

        # WHITELIST: only these pairs can communicate (bidirectional)
        self.whitelist = [
            ('00:00:00:00:00:01', '00:00:00:00:00:02'),  # h1 <-> h2
        ]

        self.logger.info("=== SDN Access Control System Started ===")
        self.logger.info("Whitelisted pairs: h1 <-> h2")
        self.logger.info("All other traffic will be BLOCKED")

    def is_authorized(self, src_mac, dst_mac):
        """Check if a src->dst pair is in the whitelist"""
        for a, b in self.whitelist:
            if (src_mac == a and dst_mac == b) or \
               (src_mac == b and dst_mac == a):
                return True
        return False

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """Install table-miss flow entry on switch connect"""
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Table-miss: send all unmatched packets to controller
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)
        self.logger.info("Switch %s connected", datapath.id)

    def add_flow(self, datapath, priority, match, actions, idle_timeout=0):
        """Helper to install a flow rule"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(
            ofproto.OFPIT_APPLY_ACTIONS, actions)]

        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=inst,
            idle_timeout=idle_timeout
        )
        datapath.send_msg(mod)

    def drop_flow(self, datapath, priority, match):
        """Install a drop rule (empty actions = drop)"""
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(
            datapath.ofproto.OFPIT_APPLY_ACTIONS, [])]

        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=inst,
            idle_timeout=30
        )
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        """Handle incoming packets - apply access control"""
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        # Parse the packet
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        dst_mac = eth.dst
        src_mac = eth.src
        dpid = datapath.id

        # Ignore LLDP
        if eth.ethertype == 0x88cc:
            return

        # Learn MAC -> port mapping
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src_mac] = in_port

        # ===== ACCESS CONTROL CHECK =====
        # Allow broadcast/multicast (ARP needs this)
        if dst_mac == 'ff:ff:ff:ff:ff:ff' or dst_mac.startswith('33:33'):
            out_port = ofproto.OFPP_FLOOD
            actions = [parser.OFPActionOutput(out_port)]
            self._send_packet(datapath, msg, in_port, actions)
            return

        # Check whitelist for unicast traffic
        if not self.is_authorized(src_mac, dst_mac):
            self.logger.warning(
                "BLOCKED: %s -> %s (unauthorized)", src_mac, dst_mac)
            # Install drop rule so future packets don't hit controller
            match = parser.OFPMatch(eth_src=src_mac, eth_dst=dst_mac)
            self.drop_flow(datapath, 10, match)
            return

        # Authorized pair - forward the packet
        self.logger.info(
            "ALLOWED: %s -> %s (authorized)", src_mac, dst_mac)

        if dst_mac in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst_mac]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # Install flow rule so future packets bypass controller
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(eth_src=src_mac, eth_dst=dst_mac)
            self.add_flow(datapath, 10, match, actions, idle_timeout=30)

        self._send_packet(datapath, msg, in_port, actions)

    def _send_packet(self, datapath, msg, in_port, actions):
        """Send packet out"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        data = msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data
        )
        datapath.send_msg(out)