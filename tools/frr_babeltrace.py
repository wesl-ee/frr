#!/usr/bin/env python3
'''
Usage: frr_babeltrace.py trace_path

FRR pushes data into lttng tracepoints in the least overhead way possible
i.e. as binary-data/crf_arrays. These traces need to be converted into pretty
strings for easy greping etc. This script is a babeltrace python plugin for
that pretty printing.

Copyright (C) 2021  NVIDIA Corporation
Anuradha Karuppiah

This program is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the Free
Software Foundation; either version 2 of the License, or (at your option)
any later version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
more details.

You should have received a copy of the GNU General Public License along
with this program; see the file COPYING; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
'''

import ipaddress
import socket
import sys

import babeltrace

########################### common parsers - start ############################
def print_ip_addr(field_val):
    '''
    pretty print "struct ipaddr"
    '''
    if field_val[0] == socket.AF_INET:
        addr = [str(fv) for fv in field_val[4:8]]
        return str(ipaddress.IPv4Address('.'.join(addr)))

    if field_val[0] == socket.AF_INET6:
        tmp = ''.join('%02x' % fb for fb in field_val[4:])
        addr = []
        while tmp:
            addr.append(tmp[:4])
            tmp = tmp[4:]
        addr = ':'.join(addr)
        return str(ipaddress.IPv6Address(addr))

    if not field_val[0]:
        return ''

    return field_val


def print_mac(field_val):
    '''
    pretty print "u8 mac[6]"
    '''
    return ':'.join('%02x' % fb for fb in field_val)

def print_net_ipv4_addr(field_val):
    '''
    pretty print ctf_integer_network ipv4
    '''
    return str(ipaddress.IPv4Address(field_val))

def print_esi(field_val):
    '''
    pretty print ethernet segment id, esi_t
    '''
    return ':'.join('%02x' % fb for fb in field_val)

def get_field_list(event):
    '''
    only fetch fields added via the TP, skip metadata etc.
    '''
    return event.field_list_with_scope(babeltrace.CTFScope.EVENT_FIELDS)

def parse_event(event, field_parsers):
    '''
    Wild card event parser; doesn't make things any prettier
    '''
    field_list = get_field_list(event)
    field_info = {}
    for field in field_list:
        if field in field_parsers:
            field_parser = field_parsers.get(field)
            field_info[field] = field_parser(event.get(field))
        else:
            field_info[field] = event.get(field)
    print(event.name, field_info)
############################ common parsers - end #############################

############################ evpn parsers - start #############################
def parse_frr_bgp_evpn_mac_ip_zsend(event):
    '''
    bgp evpn mac-ip parser; raw format -
    ctf_array(unsigned char, mac, &pfx->prefix.macip_addr.mac,
            sizeof(struct ethaddr))
    ctf_array(unsigned char, ip, &pfx->prefix.macip_addr.ip,
            sizeof(struct ipaddr))
    ctf_integer_network_hex(unsigned int, vtep, vtep.s_addr)
    ctf_array(unsigned char, esi, esi, sizeof(esi_t))
    '''
    field_parsers = {'ip': print_ip_addr,
                     'mac': print_mac,
                     'esi': print_esi,
                     'vtep': print_net_ipv4_addr}

    parse_event(event, field_parsers)

def parse_frr_bgp_evpn_bum_vtep_zsend(event):
    '''
    bgp evpn bum-vtep parser; raw format -
    ctf_integer_network_hex(unsigned int, vtep,
            pfx->prefix.imet_addr.ip.ipaddr_v4.s_addr)

    '''
    field_parsers = {'vtep': print_net_ipv4_addr}

    parse_event(event, field_parsers)

def parse_frr_bgp_evpn_mh_nh_rmac_send(event):
    '''
    bgp evpn nh-rmac parser; raw format -
    ctf_array(unsigned char, rmac, &nh->rmac, sizeof(struct ethaddr))
    '''
    field_parsers = {'rmac': print_mac}

    parse_event(event, field_parsers)

############################ evpn parsers - end #############################

def main():
    '''
    FRR lttng trace output parser; babel trace plugin
    '''
    event_parsers = {'frr_bgp:evpn_mac_ip_zsend':
                     parse_frr_bgp_evpn_mac_ip_zsend,
                     'frr_bgp:evpn_bum_vtep_zsend':
                     parse_frr_bgp_evpn_bum_vtep_zsend,
                     'frr_bgp:evpn_mh_nh_rmac_zsend':
                     parse_frr_bgp_evpn_mh_nh_rmac_send}

    # get the trace path from the first command line argument
    trace_path = sys.argv[1]

    # grab events
    trace_collection = babeltrace.TraceCollection()
    trace_collection.add_traces_recursive(trace_path, 'ctf')

    for event in trace_collection.events:
        if event.name in event_parsers:
            event_parser = event_parsers.get(event.name)
            event_parser(event)
        else:
            parse_event(event, {})

if __name__ == '__main__':
    main()
