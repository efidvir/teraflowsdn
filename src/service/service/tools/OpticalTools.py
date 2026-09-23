# Copyright 2022-2026 ETSI SDG TeraFlowSDN (TFS) (https://tfs.etsi.org/)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# 

import functools, json, logging, requests, uuid
from typing import Dict, List, Tuple
from common.method_wrappers.ServiceExceptions import NotFoundException
from common.proto.context_pb2 import(
    ConfigActionEnum, ConfigRule, ConfigRule_Custom, Connection, ContextId,
    Device, DeviceId, Empty, EndPointId, OpticalBand, OpticalBandId, OpticalBandList,
    Service, TopologyId, Uuid
)
from common.proto.pathcomp_pb2 import PathCompReply
from common.tools.context_queries.OpticalConfig import find_optical_band
from common.Constants import ServiceNameEnum 
from common.Settings import (
    ENVVAR_SUFIX_SERVICE_BASEURL_HTTP, ENVVAR_SUFIX_SERVICE_HOST, ENVVAR_SUFIX_SERVICE_PORT_GRPC,
    find_environment_variables, get_env_var_name
)
from common.tools.grpc.Tools import grpc_message_to_json_string
from common.tools.object_factory.Context import json_context_id
from common.tools.object_factory.Topology import json_topology_id
from context.client.ContextClient import ContextClient
from service.service.service_handler_api.SettingsHandler import SettingsHandler
from service.service.tools.replies import (
    reply_uni_txt, optical_band_uni_txt, reply_bid_txt, optical_band_bid_txt
)

LOGGER = logging.getLogger(__name__)

TESTING = False

get_optical_controller_setting = functools.partial(get_env_var_name, ServiceNameEnum.OPTICALCONTROLLER)
VAR_NAME_OPTICAL_CTRL_BASEURL_HTTP = get_optical_controller_setting(ENVVAR_SUFIX_SERVICE_BASEURL_HTTP)
VAR_NAME_OPTICAL_CTRL_SCHEMA       = get_optical_controller_setting('SCHEMA')
VAR_NAME_OPTICAL_CTRL_HOST         = get_optical_controller_setting(ENVVAR_SUFIX_SERVICE_HOST)
VAR_NAME_OPTICAL_CTRL_PORT         = get_optical_controller_setting(ENVVAR_SUFIX_SERVICE_PORT_GRPC)

OPTICAL_CTRL_BASE_URL = '{:s}://{:s}:{:d}/OpticalTFS'

def get_optical_controller_base_url() -> str:
    settings = find_environment_variables([
        VAR_NAME_OPTICAL_CTRL_BASEURL_HTTP,
        VAR_NAME_OPTICAL_CTRL_SCHEMA,
        VAR_NAME_OPTICAL_CTRL_HOST,
        VAR_NAME_OPTICAL_CTRL_PORT,
    ])
    base_url = settings.get(VAR_NAME_OPTICAL_CTRL_BASEURL_HTTP)
    if base_url is None:
        schema = settings.get(VAR_NAME_OPTICAL_CTRL_SCHEMA, 'http')
        host   = settings.get(VAR_NAME_OPTICAL_CTRL_HOST)
        port   = int(settings.get(VAR_NAME_OPTICAL_CTRL_PORT, 80))

        if schema is None or host is None or port is None:
            MSG = 'Missing settings for Optical Controller: settings={:s}'
            raise Exception(MSG.format(str(settings)))

        base_url = OPTICAL_CTRL_BASE_URL.format(schema, host, port)

    LOGGER.debug('Optical Controller: base_url={:s}'.format(str(base_url)))
    return base_url


def get_uuids_from_names(
    devices : List[Device], device_name : str, port_name : str
) -> Tuple[str, str]:
    for device in devices:
        if device.name != device_name: continue
        device_uuid = device.device_id.device_uuid.uuid
        for ep in device.device_endpoints:
            if ep.name != port_name: continue
            port_uuid = ep.endpoint_id.endpoint_uuid.uuid
            return device_uuid, port_uuid
    return '', ''


def get_names_from_uuids(
    devices : List[Device], device_uuid : str, port_uuid : str
) -> Tuple[str, str]:
    for device in devices:
        if device.device_id.device_uuid.uuid != device_uuid: continue
        device_name = device.name
        for ep in device.device_endpoints:
            if ep.endpoint_id.endpoint_uuid.uuid != port_uuid: continue
            port_name = ep.name
            return device_name, port_name
    return '', ''


def get_device_name_from_uuid(
    devices : List[Device], device_uuid : str
) -> str:
    for device in devices:
        if device.device_id.device_uuid.uuid != device_uuid: continue
        device_name = device.name
        return device_name
    return ''


def refresh_opticalcontroller(topology_id : Dict) -> None:
    topo_id_str = topology_id['topology_uuid']['uuid']
    cxt_id_str = topology_id['context_id']['context_uuid']['uuid']
    headers = {'Content-Type': 'application/json'}
    base_url = get_optical_controller_base_url()
    urlx = '{:s}/GetTopology/{:s}/{:s}'.format(base_url, cxt_id_str, topo_id_str)
    res = requests.get(urlx, headers=headers)
    if res is not None:
        LOGGER.debug(f"GetTopology Response {res}")


def reconfig_flex_lightpath(flow_id) -> str:
    if not TESTING:
        urlx = ""
        headers = {"Content-Type": "application/json"}
        base_url = get_optical_controller_base_url()
        urlx = "{:s}/ReconfigFlexLightpath/{}".format(base_url, flow_id)
        r = requests.put(urlx, headers=headers)
        LOGGER.debug(f"reconfig {r}")
        reply = r.text 
        return reply
    else:
        if bidir is not None:
            if bidir == 0:        
                return reply_uni_txt
        return reply_bid_txt


def add_flex_lightpath(src, dst, bitrate, bidir, pref, ob_band, dj_optical_band_id) -> str:
    if not TESTING:
        urlx = ""
        headers = {"Content-Type": "application/json"}
        base_url = get_optical_controller_base_url()
        prefs = "ANY"
        if pref != None:
            prefs = pref            
        
        if ob_band is None:
            if bidir is None:
                bidir = 1
            urlx = "{:s}/AddFlexLightpath/{:s}/{:s}/{:s}/{:s}/{:s}".format(base_url, src, dst, str(bitrate), str(prefs), str(bidir))
        else:
            if bidir is None:
                bidir = 1
            if dj_optical_band_id is None:
                urlx = "{:s}/AddFlexLightpath/{:s}/{:s}/{:s}/{:s}/{:s}/{:s}".format(base_url, src, dst, str(bitrate), str(prefs), str(bidir), str(ob_band))
            else:
                urlx = "{:s}/AddFlexLightpath/{:s}/{:s}/{:s}/{:s}/{:s}/{:s}/{:s}".format(base_url, src, dst, str(bitrate), str(prefs), str(bidir), str(ob_band), str(dj_optical_band_id))                
        r = requests.put(urlx, headers=headers)
        LOGGER.debug(f"addpathlight {r}")
        reply = r.text 
        return reply
    else:
        if bidir is not None:
            if bidir == 0:        
                return reply_uni_txt
        return reply_bid_txt

def add_alien_flex_lightpath(src, s_port, dst, d_port, band, ob_id, bidir=None) -> str:
    urlx = ""
    headers = {"Content-Type": "application/json"}
    base_url = get_optical_controller_base_url()
    #/AddAlienFLexLightpath/<string:src>/<string:s_port>/<string:dst>/<string:d_port>/<int:band>/<int:obx_idx>
    if bidir is None:
        urlx = "{:s}/AddAlienFLexLightpath/{:s}/{:s}/{:s}/{:s}/{:s}/{:s}".format(base_url, src, s_port, dst, d_port, str(band), str(ob_id))
    else:
        urlx = "{:s}/AddAlienFLexLightpath/{:s}/{:s}/{:s}/{:s}/{:s}/{:s}/{:s}".format(base_url, src, s_port, dst, d_port, str(band), str(ob_id), str(bidir))
    r = requests.put(urlx, headers=headers)
    reply = r.text 
    return reply

def add_lightpath(src, dst, bitrate, bidir) -> str:
    if not TESTING:
        urlx = ""
        headers = {"Content-Type": "application/json"}
        base_url = get_optical_controller_base_url()
        if bidir is None:
            bidir = 1
        urlx = "{:s}/AddLightpath/{:s}/{:s}/{:s}/{:s}".format(base_url, src, dst, str(bitrate), str(bidir))
        r = requests.put(urlx, headers=headers)
        LOGGER.debug(f"addpathlight {r}")
        reply = r.text 
        return reply
    else:
        if bidir is not None:
            if bidir == 0:        
                return reply_uni_txt
        return reply_bid_txt
                

def get_optical_band(idx) -> str:
    if not TESTING:
        base_url = get_optical_controller_base_url()
        urlx = '{:s}/GetOpticalBand/{:s}'.format(base_url, str(idx))
        headers = {'Content-Type': 'application/json'}
        r = requests.get(urlx, headers=headers)
        reply = r.text 
        return reply
    else:
        if str(idx) == "1":
            return optical_band_bid_txt
        else:
            return optical_band_uni_txt

    
def DelFlexLightpath( src, dst, bitrate, ob_id, flow_id=None) -> str:
    reply = {}
    code = 200
    base_url = get_optical_controller_base_url()
    if not TESTING:
        if flow_id is not None:
            if ob_id is not None :
               urlx = "{:s}/DelFlexLightpath/{}/{}/{}/{}".format(base_url, src, dst, flow_id, ob_id)
    
        else :
            #urlx = "http://{}:{}/OpticalTFS/DelOpticalBand/{}/{}/{}".format(OPTICAL_IP, OPTICAL_PORT, src, dst, ob_id)
            urlx = "{:s}/DelOpticalBandSimple/{}".format(base_url, ob_id)

        headers = {"Content-Type": "application/json"}
        r = requests.delete(urlx, headers=headers)
        reply = r.text 
        code = r.status_code
    return (reply, code)

def delete_lightpath ( src, dst, bitrate, flow_id):
    reply = "200"
    base_url = get_optical_controller_base_url()
    if not TESTING:
        urlx = "{:s}/DelLightpath/{}/{}/{}/{}".format(base_url, src, dst, bitrate, flow_id)
        headers = {"Content-Type": "application/json"}
        r = requests.delete(urlx, headers=headers)
        reply = r.text 
        code = r.status_code
    return (reply, code)

def get_lightpaths() -> str:
    base_url = get_optical_controller_base_url()
    urlx = "{:s}/GetLightpaths".format(base_url)

    headers = {"Content-Type": "application/json"}
    r = requests.get(urlx, headers=headers)
    reply = r.text 
    return reply

def adapt_reply_ob(devices, service, reply_json, context_id, topology_id, optical_band_txt) ->  PathCompReply:
    opt_reply = PathCompReply()
    topo = TopologyId(
        context_id=ContextId(context_uuid=Uuid(uuid=context_id)),
        topology_uuid=Uuid(uuid=topology_id)
    )
    #add optical band connection first
    rules_ob= []
    ob_id = 0
    connection_ob=None

    r = reply_json
    if "optical_band_id" in r.keys():
        ob_id = r["optical_band_id"]
    if "bidir" in r.keys():
        bidir_f = r["bidir"]
    else:
        bidir_f = False
    if optical_band_txt != "":
        ob_json = json.loads(optical_band_txt)
        ob = ob_json
        connection_ob = add_connection_to_reply(opt_reply)
        uuuid_x = str(uuid.uuid4())
        connection_ob.connection_id.connection_uuid.uuid = uuuid_x
        connection_ob.service_id.CopyFrom(service.service_id)
        obt = ob["band_type"]
        if obt == "l_slots":
          band_type = "L_BAND"
        elif obt == "s_slots":
          band_type = "S_BAND"
        else:
          band_type = "C_BAND"
          
        freq = ob["freq"]
        bx = ob["band"]
        #+1 is added to avoid overlap in the WSS of MGONs
        lf = int(int(freq)-int(bx/2))+1
        uf = int(int(freq)+int(bx/2))
        val_ob = {
            "band_type" : band_type,
            "low-freq"  : lf,
            "up-freq"   : uf,
            "frequency" : freq,
            "band"      : bx,
            "ob_id"     : ob_id,
            "bidir"     : bidir_f
        }
        rules_ob.append(ConfigRule_Custom(resource_key="/settings-ob_{}".format(uuuid_x), resource_value=json.dumps(val_ob)))
        bidir_ob = ob["bidir"]
        # in case the service is built upon existed optical band , don't clacluate the endpoints of it 
        for devxb in ob["flows"].keys():
            LOGGER.debug("optical-band device {}".format(devxb))
            in_end_point_b = "0"
            out_end_point_b = "0"
            in_end_point_f = ob["flows"][devxb]["f"]["in"]
            out_end_point_f = ob["flows"][devxb]["f"]["out"]
            LOGGER.debug("optical-band ports {}, {}".format(in_end_point_f, out_end_point_f))
            if bidir_ob:
                in_end_point_b = ob["flows"][devxb]["b"]["in"]
                out_end_point_b = ob["flows"][devxb]["b"]["out"]
                LOGGER.debug("optical-band ports {}, {}".format(in_end_point_b, out_end_point_b))
            #if (in_end_point_f == "0" or out_end_point_f == "0") and (in_end_point_b == "0" or out_end_point_b == "0"):
            if in_end_point_f != "0":
                d_ob, p_ob = get_uuids_from_names(devices, devxb, in_end_point_f)
                if d_ob != "" and p_ob != "":
                    end_point_b = EndPointId(topology_id=topo, device_id=DeviceId(device_uuid=Uuid(uuid=d_ob)), endpoint_uuid=Uuid(uuid=p_ob))
                    connection_ob.path_hops_endpoint_ids.add().CopyFrom(end_point_b)
                else:
                    LOGGER.info("no map device port for device {} port {}".format(devxb, in_end_point_f))

            if out_end_point_f != "0":
                d_ob, p_ob = get_uuids_from_names(devices, devxb, out_end_point_f)
                if d_ob != "" and p_ob != "":
                    end_point_b = EndPointId(topology_id=topo, device_id=DeviceId(device_uuid=Uuid(uuid=d_ob)), endpoint_uuid=Uuid(uuid=p_ob))
                    connection_ob.path_hops_endpoint_ids.add().CopyFrom(end_point_b) 
                else:
                    LOGGER.info("no map device port for device {} port {}".format(devxb, out_end_point_f))
            if in_end_point_b != "0":
                d_ob, p_ob = get_uuids_from_names(devices, devxb, in_end_point_b)
                if d_ob != "" and p_ob != "":
                    end_point_b = EndPointId(topology_id=topo, device_id=DeviceId(device_uuid=Uuid(uuid=d_ob)), endpoint_uuid=Uuid(uuid=p_ob))
                    connection_ob.path_hops_endpoint_ids.add().CopyFrom(end_point_b) 
                else:
                    LOGGER.info("no map device port for device {} port {}".format(devxb, in_end_point_b))
            if out_end_point_b != "0":
                d_ob, p_ob = get_uuids_from_names(devices, devxb, out_end_point_b)
                if d_ob != "" and p_ob != "":
                    end_point_b = EndPointId(topology_id=topo, device_id=DeviceId(device_uuid=Uuid(uuid=d_ob)), endpoint_uuid=Uuid(uuid=p_ob))
                    connection_ob.path_hops_endpoint_ids.add().CopyFrom(end_point_b)
                else:
                    LOGGER.info("no map device port for device {} port {}".format(devxb, out_end_point_b))
            LOGGER.debug("optical-band connection {}".format(connection_ob))
        #check that list of endpoints is not empty  
        if connection_ob is not None and  len(connection_ob.path_hops_endpoint_ids) == 0:
            LOGGER.debug("deleting empty optical-band connection")
            opt_reply.connections.remove(connection_ob)

        '''
        #inizialize custom optical parameters
        band = r["band"] if "band" in r else None
        op_mode = r["op-mode"] if "op-mode" in r else None
        frequency = r["freq"] if "freq" in r else None
        flow_id = r["flow_id"] if "flow_id" in r else None
        r_type = r["band_type"] if "band_type" in r else None
        if r_type == "l_slots":
            band_type = "L_BAND"
        elif r_type == "s_slots":
            band_type = "S_BAND"
        else:
            band_type = "C_BAND"
        if ob_id != 0:
            val = {"target-output-power": "1.0", "frequency": frequency, "operational-mode": op_mode, "band": band, "flow_id": flow_id, "ob_id": ob_id, "band_type": band_type, "bidir": bidir_f}
        else:
            val = {"target-output-power": "1.0", "frequency": frequency, "operational-mode": op_mode, "band": band, "flow_id": flow_id, "band_type": band_type, "bidir": bidir_f}
        custom_rule = ConfigRule_Custom(resource_key="/settings", resource_value=json.dumps(val))
        rule = ConfigRule(action=ConfigActionEnum.CONFIGACTION_SET, custom=custom_rule)
        service.service_config.config_rules.add().CopyFrom(rule)
        '''
   
        if len(rules_ob) > 0:
            for rulex in rules_ob:
                rule_ob = ConfigRule(action=ConfigActionEnum.CONFIGACTION_SET, custom=rulex)
                service.service_config.config_rules.add().CopyFrom(rule_ob)

        opt_reply.services.add().CopyFrom(service)   
    return opt_reply



def adapt_reply(
    devices, service, reply_json, context_id : str, topology_id : str, optical_band_txt
) ->  PathCompReply:
    opt_reply = PathCompReply()
    topo = TopologyId(**json_topology_id(topology_id, context_id=json_context_id(context_id)))

    #add optical band connection first
    rules_ob = []
    ob_id = 0
    connection_ob = None

    r = reply_json
    if "parent_opt_band" in r.keys():
        ob_id = r["parent_opt_band"]
    if "bidir" in r.keys():
        bidir_f = r["bidir"]
    else:
        bidir_f = False
    if optical_band_txt != "":
        ob_json = json.loads(optical_band_txt)
        ob = ob_json
        connection_ob = add_connection_to_reply(opt_reply)
        uuuid_x = str(uuid.uuid4())
        connection_ob.connection_id.connection_uuid.uuid = uuuid_x
        connection_ob.service_id.CopyFrom(service.service_id)
        new_ob = r["new_optical_band"] if 'new_optical_band' in r else None
        ob_id = ob["optical_band_id"]        
        obt = ob["band_type"]
        if obt == "l_slots":
          band_type = "L_BAND"
        elif obt == "s_slots":
          band_type = "S_BAND"
        else:
          band_type = "C_BAND"
          
        freq = ob["freq"]
        bx = ob["band"]
        #+1 is added to avoid overlap in the WSS of MGONs
        lf = int(int(freq)-int(bx/2))+1
        uf = int(int(freq)+int(bx/2))
        val_ob = {
            "band_type" : band_type,
            "low-freq"  : lf,
            "up-freq"   : uf,
            "frequency" : freq,
            "band"      : bx,
            "ob_id"     : ob_id,
            "bidir"     : bidir_f
        }
        rules_ob.append(ConfigRule_Custom(resource_key="/settings-ob_{}".format(uuuid_x), resource_value=json.dumps(val_ob)))
        bidir_ob = ob["bidir"]
        # in case the service is built upon existed optical band , don't clacluate the endpoints of it 
        if new_ob != 2 : 
            for devxb in ob["flows"].keys():
                LOGGER.debug("optical-band device {}".format(devxb))
                in_end_point_b = "0"
                out_end_point_b = "0"
                in_end_point_f = ob["flows"][devxb]["f"]["in"]
                out_end_point_f = ob["flows"][devxb]["f"]["out"]
                LOGGER.debug("optical-band ports {}, {}".format(in_end_point_f, out_end_point_f))
                if bidir_ob:
                    in_end_point_b = ob["flows"][devxb]["b"]["in"]
                    out_end_point_b = ob["flows"][devxb]["b"]["out"]
                    LOGGER.debug("optical-band ports {}, {}".format(in_end_point_b, out_end_point_b))
                #if (in_end_point_f == "0" or out_end_point_f == "0") and (in_end_point_b == "0" or out_end_point_b == "0"):
                if in_end_point_f != "0":
                    d_ob, p_ob = get_uuids_from_names(devices, devxb, in_end_point_f)
                    if d_ob != "" and p_ob != "":
                        end_point_b = EndPointId(topology_id=topo, device_id=DeviceId(device_uuid=Uuid(uuid=d_ob)), endpoint_uuid=Uuid(uuid=p_ob))
                        connection_ob.path_hops_endpoint_ids.add().CopyFrom(end_point_b)
                    else:
                        LOGGER.info("no map device port for device {} port {}".format(devxb, in_end_point_f))

                if out_end_point_f != "0":
                    d_ob, p_ob = get_uuids_from_names(devices, devxb, out_end_point_f)
                    if d_ob != "" and p_ob != "":
                        end_point_b = EndPointId(topology_id=topo, device_id=DeviceId(device_uuid=Uuid(uuid=d_ob)), endpoint_uuid=Uuid(uuid=p_ob))
                        connection_ob.path_hops_endpoint_ids.add().CopyFrom(end_point_b) 
                    else:
                        LOGGER.info("no map device port for device {} port {}".format(devxb, out_end_point_f))
                if in_end_point_b != "0":
                    d_ob, p_ob = get_uuids_from_names(devices, devxb, in_end_point_b)
                    if d_ob != "" and p_ob != "":
                        end_point_b = EndPointId(topology_id=topo, device_id=DeviceId(device_uuid=Uuid(uuid=d_ob)), endpoint_uuid=Uuid(uuid=p_ob))
                        connection_ob.path_hops_endpoint_ids.add().CopyFrom(end_point_b) 
                    else:
                        LOGGER.info("no map device port for device {} port {}".format(devxb, in_end_point_b))
                if out_end_point_b != "0":
                    d_ob, p_ob = get_uuids_from_names(devices, devxb, out_end_point_b)
                    if d_ob != "" and p_ob != "":
                        end_point_b = EndPointId(topology_id=topo, device_id=DeviceId(device_uuid=Uuid(uuid=d_ob)), endpoint_uuid=Uuid(uuid=p_ob))
                        connection_ob.path_hops_endpoint_ids.add().CopyFrom(end_point_b)
                    else:
                        LOGGER.info("no map device port for device {} port {}".format(devxb, out_end_point_b))
                LOGGER.debug("optical-band connection {}".format(connection_ob))
        
    connection_f = add_connection_to_reply(opt_reply)
    connection_f.connection_id.connection_uuid.uuid = str(uuid.uuid4())
    connection_f.service_id.CopyFrom(service.service_id)
    for devx in r["flows"].keys():
        LOGGER.debug("lightpath device {}".format(devx))
        in_end_point_b = "0"
        out_end_point_b = "0"
        
        in_end_point_f = r["flows"][devx]["f"]["in"]
        out_end_point_f = r["flows"][devx]["f"]["out"]
        LOGGER.debug("lightpath ports {}, {}".format(in_end_point_f, out_end_point_f))
        if bidir_f:
            in_end_point_b = r["flows"][devx]["b"]["in"]
            out_end_point_b = r["flows"][devx]["b"]["out"]
            LOGGER.debug("lightpath ports {}, {}".format(in_end_point_b, out_end_point_b))
        if in_end_point_f != "0":
            d, p = get_uuids_from_names(devices, devx, in_end_point_f)
            if d != "" and p != "":
                end_point = EndPointId(topology_id=topo, device_id=DeviceId(device_uuid=Uuid(uuid=d)), endpoint_uuid=Uuid(uuid=p))
                connection_f.path_hops_endpoint_ids.add().CopyFrom(end_point) 
            else:
                LOGGER.info("no map device port for device {} port {}".format(devx, in_end_point_f))
        if out_end_point_f != "0":
            d, p = get_uuids_from_names(devices, devx, out_end_point_f)
            if d != "" and p != "":
                end_point = EndPointId(topology_id=topo, device_id=DeviceId(device_uuid=Uuid(uuid=d)), endpoint_uuid=Uuid(uuid=p))
                connection_f.path_hops_endpoint_ids.add().CopyFrom(end_point)
            else:
                LOGGER.info("no map device port for device {} port {}".format(devx, out_end_point_f))
        if in_end_point_b != "0":
            d, p = get_uuids_from_names(devices, devx, in_end_point_b)
            if d != "" and p != "":
                end_point = EndPointId(topology_id=topo, device_id=DeviceId(device_uuid=Uuid(uuid=d)), endpoint_uuid=Uuid(uuid=p))
                connection_f.path_hops_endpoint_ids.add().CopyFrom(end_point) 
            else:
                LOGGER.info("no map device port for device {} port {}".format(devx, in_end_point_b))
        if out_end_point_b != "0":
            d, p = get_uuids_from_names(devices, devx, out_end_point_b)
            if d != "" and p != "":
                end_point = EndPointId(topology_id=topo, device_id=DeviceId(device_uuid=Uuid(uuid=d)), endpoint_uuid=Uuid(uuid=p))
                connection_f.path_hops_endpoint_ids.add().CopyFrom(end_point) 
            else:
                LOGGER.info("no map device port for device {} port {}".format(devx, out_end_point_b))

    #check that list of endpoints is not empty  
    if connection_ob is not None and  len(connection_ob.path_hops_endpoint_ids) == 0:
        LOGGER.debug("deleting empty optical-band connection")
        opt_reply.connections.remove(connection_ob)

    #inizialize custom optical parameters
    band = r["band"] if "band" in r else None
    op_mode = r["op-mode"] if "op-mode" in r else None
    frequency = r["freq"] if "freq" in r else None
    flow_id = r["flow_id"] if "flow_id" in r else None
    r_type = r["band_type"] if "band_type" in r else None
    if r_type == "l_slots":
        band_type = "L_BAND"
    elif r_type == "s_slots":
        band_type = "S_BAND"
    else:
        band_type = "C_BAND"
        
    if ob_id != 0:
        val = {"target-output-power": "1.0", "frequency": frequency, "operational-mode": op_mode, "band": band, "flow_id": flow_id, "ob_id": ob_id, "band_type": band_type, "bidir": bidir_f}
    else:
        val = {"target-output-power": "1.0", "frequency": frequency, "operational-mode": op_mode, "band": band, "flow_id": flow_id, "band_type": band_type, "bidir": bidir_f}
    custom_rule = ConfigRule_Custom(resource_key="/settings", resource_value=json.dumps(val))
    rule = ConfigRule(action=ConfigActionEnum.CONFIGACTION_SET, custom=custom_rule)
    service.service_config.config_rules.add().CopyFrom(rule)
   
    if len(rules_ob) > 0:
        if new_ob != 2 :
            for rulex in rules_ob:
                rule_ob = ConfigRule(action=ConfigActionEnum.CONFIGACTION_SET, custom=rulex)
                service.service_config.config_rules.add().CopyFrom(rule_ob)

    opt_reply.services.add().CopyFrom(service)   
    return opt_reply


def add_service_to_reply(reply : PathCompReply, service : Service) -> Service:
    service_x = reply.services.add()
    service_x.CopyFrom(service)
    return service_x


def add_connection_to_reply(reply : PathCompReply) -> Connection:
    return reply.connections.add()


def update_config_rules(
    service : Service, config_to_update : Dict
) -> Service:
    config_rules = service.service_config.config_rules
    if len(config_rules) == 0 : return service
    for key, new_value in config_to_update.items():
        for c in config_rules:
            if c.custom.resource_key != key: continue
            c.custom.resource_value = json.dumps(new_value)
    return service


def extend_optical_band(reply, optical_band_text) -> Service:
    LOGGER.debug('[extend_optical_band] optical-band extended {:s}'.format(str(reply)))
    LOGGER.debug('[extend_optical_band] optical-band_text {:s}'.format(str(optical_band_text)))

    optical_band_res = json.loads(optical_band_text)
    if 'optical_band_id' not in optical_band_res:
        MSG = 'optical_band_id not found in reply({:s})/optical_band_text({:s})'
        raise KeyError(MSG.format(str(reply), str(optical_band_text)))

    context_client = ContextClient()
    optical_bands : OpticalBandList = context_client.GetOpticalBand(Empty())
    LOGGER.warning('GetOpticalBand result: {:s}'.format(grpc_message_to_json_string(optical_bands)))

    ob_index = optical_band_res['optical_band_id']
    optical_band = find_optical_band(ob_index=ob_index)
    if optical_band is None:
        raise NotFoundException('OpticalBand', str(ob_index), extra_details=[
            'optical_band_text={:s}'.format(str(optical_band_text)),
            'reply={:s}'.format(str(reply))
        ])

    service = optical_band.service
    connection_uuid = optical_band.connection_id.connection_uuid.uuid

    setting_handler = SettingsHandler(service.service_config)

    setting_key_svc = '/settings'
    setting_key_ob  = '/settings-ob_{:s}'.format(connection_uuid)

    config_svc = setting_handler.get(setting_key_svc)
    config_ob  = setting_handler.get(setting_key_ob )

    band = optical_band_res['band']
    frequency = optical_band_res['freq']
    config_ob.value['band'     ] = band
    config_ob.value['frequency'] = frequency
    config_ob.value['low-freq' ] = int(frequency - (band/2))
    config_ob.value['up-freq'  ] = int(frequency + (band/2))

    config_svc.value['ob-expanded'] = 1

    MSG = '[extend_optical_band] service before setting config {:s}'
    LOGGER.debug(MSG.format(grpc_message_to_json_string(service)))

    config_to_update = {
        setting_key_svc : config_svc.value,
        setting_key_ob  : config_ob.value
    }

    MSG = '[extend_optical_band] config_to_update={:s}'
    LOGGER.debug(MSG.format(str(config_to_update)))

    service = update_config_rules(service, config_to_update)
    return service
