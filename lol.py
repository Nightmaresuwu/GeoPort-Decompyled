# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: main-win.py
# Bytecode version: 3.11a7e (3495)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

global rsd_port  # inserted
global udid  # inserted
global lockdown  # inserted
global wifi_address  # inserted
global pair_record  # inserted
global terminate_tunnel_thread  # inserted
global chosen_port  # inserted
global user_locale  # inserted
global ios_version  # inserted
global location  # inserted
global terminate_location_thread  # inserted
global rsd_host  # inserted
global connection_type  # inserted
global api_data  # inserted
global rsd_data  # inserted
global wifi_port  # inserted
import locale
import os
import re
import sys
import time
import pyuac
import psutil
import signal
import socket
import random
import asyncio
import argparse
import requests
import threading
import webbrowser
import subprocess
import pycountry
from flask import Flask, jsonify, render_template, request
from urllib3.exceptions import InsecureRequestWarning, ConnectionError
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
from contextlib import asynccontextmanager
from pymobiledevice3.usbmux import list_devices
from pymobiledevice3.cli.mounter import auto_mount
from pymobiledevice3.lockdown import create_using_usbmux, create_using_tcp, get_mobdev2_lockdowns
from pymobiledevice3.services.amfi import AmfiService
from pymobiledevice3.exceptions import DeviceHasPasscodeSetError, NoDeviceConnectedError
from pymobiledevice3.services.dvt.dvt_secure_socket_proxy import DvtSecureSocketProxyService
from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation
from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService
from pymobiledevice3.remote.utils import stop_remoted_if_required, resume_remoted_if_required, get_rsds
from pymobiledevice3.remote.tunnel_service import create_core_device_tunnel_service_using_rsd, get_remote_pairing_tunnel_services, start_tunnel, create_core_device_tunnel_service_using_remotepairing, get_core_device_tunnel_services, CoreDeviceTunnelProxy
from pymobiledevice3.osu.os_utils import get_os_utils
from pymobiledevice3.bonjour import DEFAULT_BONJOUR_TIMEOUT, browse_mobdev2
from pymobiledevice3.pair_records import get_local_pairing_record, get_remote_pairing_record_filename, get_preferred_pair_record
from pymobiledevice3.common import get_home_folder
from pymobiledevice3.cli.remote import cli_install_wetest_drivers
from pymobiledevice3.cli.remote import tunnel_task
from pymobiledevice3.lockdown import LockdownClient
from pymobiledevice3.lockdown_service_provider import LockdownServiceProvider
from pymobiledevice3.remote.common import TunnelProtocol
parser = argparse.ArgumentParser()
parser.add_argument('--no-browser', action='store_true', help='Skip auto opening the browser')
parser.add_argument('--port', type=int, help='Specify port number to listen on for web browser requests')
args = parser.parse_args()
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
OSUTILS = get_os_utils()
import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])
logger = logging.getLogger('GeoPort')
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('werkzeug').disabled = True
app = Flask(__name__)
home_dir = os.path.expanduser('~')
is_windows = sys.platform == 'win32'
base_directory = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(sys.argv[0])))
flask_port = 54321
api_url = 'https://projectzerothree.info/api.php?format=json'
api_data = None
user_locale = None
location = None
rsd_data = None
rsd_host = None
rsd_port = None
rsd_data_map = {}
wifi_address = None
wifi_port = None
connection_type = None
udid = None
lockdown = None
ios_version = None
pair_record = None
error_message = None
sudo_message = ''
captured_output = None
GITHUB_REPO = 'davesc63/GeoPort'
CURRENT_VERSION_FILE = 'CURRENT_VERSION'
BROADCAST_FILE = 'BROADCAST'
APP_VERSION_NUMBER = '2.3.3'
APP_VERSION_TYPE = 'fuel'
terminate_tunnel_thread = False
terminate_location_thread = False
location_threads = []
timeout = DEFAULT_BONJOUR_TIMEOUT
current_platform = sys.platform
platform = {'win32': 'Windows', 'linux': 'Linux', 'darwin': 'MacOS'}.get(current_platform, 'Unknown')
if current_platform == 'darwin':
    if os.geteuid()!= 0:
        logger.error('*********************** WARNING ***********************')
        logger.error('Not running as Sudo, this probably isn\'t going to work')
        logger.error('*********************** WARNING ***********************')
        sudo_message = 'Not running as Sudo, this probably isn\'t going to work'
    else:  # inserted
        logger.info('Running as Sudo')
        sudo_message = ''

def fetch_api_data(api_url):
    global api_data  # inserted
    try:
        api_data = requests.get(api_url, verify=False).json()
        return api_data
    except requests.exceptions.RequestException as e:
        logger.error(f'Error: {e}')
        logger.error('API is unreachable or there was an error during the request')
        logger.error('Sorry - Fuel data is not available')
    except ConnectionError as e:
        logger.error('Error: Name resolution failed.')
        logger.error('Please check your internet connection or the correctness of the API URL.')
        logger.error('Sorry - Fuel data is not available')
        logger.error(f'Details: {e}')

def create_geoport_folder():
    geoport_folder = os.path.join(home_dir, 'GeoPort')
    if not os.path.exists(geoport_folder):
        os.makedirs(geoport_folder)
        logger.info(f'GeoPort Home: {geoport_folder}')
        logger.info('GeoPort folder created successfully')
    if current_platform == 'win32':
        os.system(f'icacls {geoport_folder} /grant Everyone:(OI)(CI)F')
        logger.info('Permissions set for GeoPort folder on Windows')
    else:  # inserted
        os.chmod(geoport_folder, 511)
        logger.info('Permissions set for GeoPort folder on MacOS')

def run_tunnel(service_provider):
    try:
        asyncio.run(start_quic_tunnel(service_provider))
        logger.info('run_tun completed')
        sys.exit(0)
    except Exception as e:
        error_message = str(e)
        with app.app_context():
            return jsonify({'error': error_message})

def start_tunnel_thread(service_provider):
    global terminate_tunnel_thread  # inserted
    terminate_tunnel_thread = False
    thread = threading.Thread(target=run_tunnel, args=(service_provider,))
    thread.start()

async def start_quic_tunnel(service_provider: RemoteServiceDiscoveryService) -> None:
    global rsd_host  # inserted
    global rsd_port  # inserted
    logger.warning('Start USB QUIC tunnel')
    stop_remoted_if_required()
    service = await create_core_device_tunnel_service_using_rsd(service_provider, autopair=True)
    async with service.start_quic_tunnel() as tunnel_result:
        resume_remoted_if_required()
        logger.info(f'QUIC Address: {tunnel_result.address}')
        logger.info(f'QUIC Port: {tunnel_result.port}')
        rsd_host = tunnel_result.address
        rsd_port = str(tunnel_result.port)
        while True:
            if terminate_tunnel_thread is True:
                return
            else:  # inserted
                await asyncio.sleep(0.5)

def run_tcp_tunnel(service_provider):
    try:
        asyncio.run(start_tcp_tunnel(service_provider))
        logger.info('run_tun completed')
        sys.exit(0)
    except Exception as e:
        error_message = str(e)
        with app.app_context():
            return jsonify({'error': error_message})

def start_tcp_tunnel_thread(service_provider):
    global terminate_tunnel_thread  # inserted
    terminate_tunnel_thread = False
    thread = threading.Thread(target=run_tcp_tunnel, args=(service_provider,))
    thread.start()

async def start_tcp_tunnel(service_provider: CoreDeviceTunnelProxy) -> None:
    global rsd_host  # inserted
    global rsd_port  # inserted
    logger.warning('Start USB TCP tunnel')
    stop_remoted_if_required()
    lockdown = create_using_usbmux(udid, autopair=True)
    service = CoreDeviceTunnelProxy(lockdown)
    async with service.start_tcp_tunnel() as tunnel_result:
        logger.info(f'TCP Address: {tunnel_result.address}')
        logger.info(f'TCP Port: {tunnel_result.port}')
        rsd_host = tunnel_result.address
        rsd_port = str(tunnel_result.port)
        while True:
            if terminate_tunnel_thread is True:
                return
            else:  # inserted
                await asyncio.sleep(0.5)

def is_major_version_17_or_greater(version_string):
    try:
        major_version = int(version_string.split('.')[0])
        return major_version >= 17
    except (ValueError, IndexError):
        return False

def is_major_version_less_than_16(version_string):
    try:
        major_version = int(version_string.split('.')[0])
        return major_version < 16
    except (ValueError, IndexError):
        logger.error(f'Error: {ValueError}, {IndexError}')
        return False

def version_check(version_string):
    try:
        version_parts = version_string.split('.')
        major_version = int(version_parts[0])
        minor_version = int(version_parts[1]) if len(version_parts) > 1 else 0
        if major_version == 17 and 0 <= minor_version <= 3:
            if sys.platform == 'win32':
                logger.info('Checking Windows Driver requirement')
                logger.info('Driver is required')
            return True
        if sys.platform == 'win32':
            logger.info('Driver is not required')
            return False
        else:  # this should be part of the if-else structure above
            logger.info('MacOS - pass')
            return False
    except (ValueError, IndexError) as e:
        logger.error(f'Driver check error: {e}')


def get_user_country():
    global user_locale  # inserted
    try:
        user_locale, _ = locale.getlocale()
        if user_locale is None:
            logger.warning('User locale is None. Defaulting to IP geolocation service.')
            return get_country_from_ip()

        country_code = user_locale.split('_')[-1]  # Corrected indexing
        country = pycountry.countries.get(alpha_2=country_code)
        country_name = country.name if country else None

        if country_name is None:
            logger.warning('Failed to retrieve country name using locale. Using IP geolocation service.')
            return get_country_from_ip()

        return country_name  # This should be returned directly without else
    except Exception as e:
        logger.error(f'Error getting user country: {e}')
        return None  # Optionally return None in case of error


def get_country_from_ip():
    try:
        response = requests.get('http://ip-api.com/json/')
        if response.status_code == 200:
            data = response.json()
            country_name = data.get('country')
            if country_name:
                return country_name
            logger.warning('Failed to retrieve country name from IP geolocation service.')
        logger.error(f'Error: Unable to retrieve data. Status code: {response.status_code}')
        logger.warning('Setting to default country')
        country_name = 'Spain'
        return country_name
    except Exception as e:
        logger.error(f'Error getting country from IP geolocation service: {e}')
        country_name = 'Spain'
        return country_name

def get_devices_with_retry(max_attempts=10):
    if sys.platform == 'win32':
        logger.info(f'iOS Version: {ios_version}')
        if version_check(ios_version):
            logger.info('Windows Driver Install Required')
            cli_install_wetest_drivers()
    for attempt in range(1, max_attempts + 1):
        try:
            devices = asyncio.run(get_rsds(timeout))
            if devices:
                return devices
            logger.warning(f'Attempt {attempt}: No devices found')
        except Exception as e:
                logger.warning(f'Attempt {attempt}: Error occurred - {e}')
        time.sleep(1)
    else:  # inserted
        raise RuntimeError('No devices found after multiple attempts.\n Ensure you are running GeoPort as sudo / Administrator \n Please see the FAQ: https://github.com/davesc63/GeoPort/blob/main/FAQ.md \n If you still have the error please raise an issue on github: https://github.com/davesc63/GeoPort/issues ')

def get_wifi_with_retry(max_attempts=10):
    global wifi_address  # inserted
    global wifi_port  # inserted
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info('Discovering Wifi Devices - This may take a while...')
            devices = asyncio.run(get_remote_pairing_tunnel_services(timeout))
            if devices:
                if udid:
                    for device in devices:
                        if device.remote_identifier == udid:
                            logger.info(f'Device found with udid: {udid}.')
                            wifi_address = device.hostname
                            wifi_port = device.port
                            return device
                else:  # inserted
                    return devices
            else:  # inserted
                logger.warning(f'Attempt {attempt}: No devices found')
        except Exception as e:
                    logger.warning(f'Attempt {attempt}: Error occurred - {e}')
        time.sleep(1)
    else:  # inserted
        raise RuntimeError('No devices found after multiple attempts. Please see the FAQ.')

@app.route('/stop_tunnel', methods=['POST'])
def stop_tunnel_thread():
    global terminate_tunnel_thread  # inserted
    logger.info('stop tunnel thread')
    terminate_tunnel_thread = True
    return jsonify('Tunnel stopped')

@app.route('/api/data/<fuel_type>')
def get_fuel_type_data(fuel_type):
    selected_fuel_region = request.args.get('region', 'All')
    if api_data is None:
        logger.error('API Data is none, Fuel data is not available')
        return (jsonify({}), 500)
    all_region_data = next((region['prices'] for region in api_data['regions'] if region['region'] == selected_fuel_region), [])
    selected_data = next((entry for entry in all_region_data if entry['type'] == fuel_type), None)
    return jsonify(selected_data)

@app.route('/api/fuel_types')
def get_fuel_types():
    selected_fuel_region = request.args.get('region', 'All')
    if api_data is None:
        logger.error('API Data is none, sorry - Fuel data is not available')
        return (jsonify({}), 500)
    all_region_data = next((region['prices'] for region in api_data['regions'] if region['region'] == selected_fuel_region), [])
    fuel_types = set((entry['type'] for entry in all_region_data))
    return jsonify(list(fuel_types))

@app.route('/update_location', methods=['POST'])
def update_location():
    global location  # inserted
    data = request.get_json()
    lat = float(data['lat'])
    lng = float(data['lng'])
    location = f'{lat} {lng}'
    return 'Location updated successfully'

def check_pair_record(udid):
    global pair_record  # inserted
    logger.info(f'Connection Type: {connection_type}')
    logger.info('Enable Developer Mode')
    home = get_home_folder()
    logger.info(f'Pair Record Home: {home}')
    filename = get_remote_pairing_record_filename(udid)
    logger.info(f'Pair Record File: {filename}')
    pair_record = get_preferred_pair_record(udid, home)
    return pair_record

def check_developer_mode(udid, connection_type):
    try:
        logger.warning('Check Developer Mode')
        lockdown = create_using_usbmux(udid, connection_type=connection_type, autopair=True)
        result = lockdown.developer_mode_status
        logger.info(f'Developer Mode Check result:  {result}')
        if result:
            logger.info('Developer Mode is true')
            return True
        logger.warning('Developer Mode is false')
        return False
    except subprocess.CalledProcessError as e:
        return False

def enable_developer_mode(udid, connection_type):
    check_pair_record(udid)
    logger.info(f'Connection Type: {connection_type}')
    logger.info('Enable Developer Mode')
    home = get_home_folder()
    logger.info(f'Pair Record Home: {home}')
    if connection_type == 'Network':
        if pair_record is None:
            logger.error('Network: No Pair Record Found. Please use a USB cable first to create a pair record')
            return (False, 'No Pair Record Found. Please use a USB cable first to create a pair record')
    else:  # inserted
        logger.error('No Pair Record Found. USB cable detected. Creating a pair record')
        pass
    lockdown = create_using_usbmux(udid, connection_type=connection_type, autopair=True, pairing_records_cache_folder=home)
    try:
        AmfiService(lockdown).enable_developer_mode()
        logger.info('Enable complete, mount developer image...')
        mount_developer_image()
    except DeviceHasPasscodeSetError:
        error_message = 'Error: Device has a passcode set\n \n Please temporarily remove the passcode and run GeoPort again to enable Developer Mode \n \n Go to \"Settings - Face ID & Passcode\"\n'
        logger.error(f'{error_message}')
        return (False, error_message)
    return (True, None)

@app.route('/enable_developer_mode', methods=['POST'])
def enable_developer_mode_route():
    global udid  # inserted
    try:
        data = request.get_json()
        udid = data.get('udid', None)
        success, error_message = enable_developer_mode(udid, connection_type)
        if success:
            return jsonify({'success': True, 'udid': udid})
        return jsonify({'error': error_message})
    except Exception as e:
        error_message = str(e)
        return jsonify({'error': error_message})

@app.route('/connect_device', methods=['POST'])
def connect_device():
    global rsd_data  # inserted
    global connection_type  # inserted
    global rsd_host  # inserted
    global udid  # inserted
    global rsd_port  # inserted
    data = request.get_json()
    logger.info(f'Connect Device Data: {data}')
    udid = data.get('udid', None)
    connection_type = data.get('connType')
    if udid in rsd_data_map:
        if connection_type in rsd_data_map[udid]:
            logger.info(f'Connect_Device Map - Looking for {udid} in {connection_type}')
            rsd_data = rsd_data_map[udid][connection_type]
            rsd_host = rsd_data['host']
            rsd_port = rsd_data['port']
            logger.info(f'RSD in udid mapping is: {rsd_data}')
            logger.info('RSD already created. Reusing connection')
            logger.info(f'RSD Data: {rsd_data}')
            return jsonify({'rsd_data': rsd_data})
        logger.info(f'No matching RSD entry found for udid: {udid} and connection type: {connection_type}')
    if not check_developer_mode(udid, connection_type):
        return jsonify({'developer_mode_required': 'True'})
    if connection_type == 'USB':
        return connect_usb(data)
    if connection_type == 'Network':
        check_pair_record(udid)
        if pair_record is None:
            logger.error('No Pair Record Found. Please use a USB Cable to create one')
            return jsonify({'Error': 'No Pair Record Found'})
        result = connect_wifi(data)
        return result
    logger.error('Error: No matching connection type')
    return jsonify({'Error': 'No matching connection type'})

def check_rsd_data():
    max_attempts = 30
    attempts = 0
    while attempts < max_attempts:
        if rsd_host is not None and rsd_port is not None:
            return True
        time.sleep(1)
        attempts += 1
    return False

def connect_usb(data):
    global rsd_data  # inserted
    global connection_type  # inserted
    global rsd_host  # inserted
    global ios_version  # inserted
    global lockdown  # inserted
    global udid  # inserted
    global rsd_port  # inserted
    try:
        logger.info(f'USB data: {data}')
        udid = data.get('udid', None)
        ios_version = data.get('ios_version')
        connection_type = data.get('connType')
        rsd_host = None
        rsd_port = None
        
        if ios_version is not None and is_major_version_17_or_greater(ios_version):
            logger.info('iOS 17+ detected')
            logger.info(f'iOS Version: {ios_version}')
            
            if version_check(ios_version):
                if sys.platform == 'win32':
                    logger.warning('iOS is between 17.0 and 17.3.1, WHY?')
                    logger.warning('You should upgrade to 17.4+')
                    logger.error('We need to install a 3rd party driver for these versions')
                    logger.error('which may stop working at any time')

                try:
                    devices = get_devices_with_retry()
                    logger.info(f'Devices: {devices}')
                    rsd = [device for device in devices if device.udid == udid]
                    if len(rsd) > 0:
                        rsd = rsd[0]
                    start_tunnel_thread(rsd)
                except RuntimeError as e:
                    error_message = str(e)
                    logger.error(f'Error: {error_message}')
                    return jsonify({'error': 'No Devices Found'})
                
                logger.warning('ios <17.4 on non-windows')
                try:
                    devices = get_devices_with_retry()
                    logger.info(f'Devices: {devices}')
                    rsd = [device for device in devices if device.udid == udid]
                    if len(rsd) > 0:
                        rsd = rsd[0]
                    start_tunnel_thread(rsd)
                except RuntimeError as e:
                    error_message = str(e)
                    logger.error(f'Error: {error_message}')
                    return jsonify({'error': 'No Devices Found'})

            lockdown = create_using_usbmux(udid, autopair=True)
            logger.info(f'Create Lockdown {lockdown}')
            start_tcp_tunnel_thread(lockdown)
            if not check_rsd_data():
                logger.error('RSD Data is None, Perhaps the tunnel isn\'t established')
            else:
                rsd_data = (rsd_host, rsd_port)
                logger.info(f'RSD Data: {rsd_data}')
                
            rsd_data_map.setdefault(udid, {})[connection_type] = {'host': rsd_host, 'port': rsd_port}
            logger.info(f'Device Connection Map: {rsd_data_map}')
            return jsonify({'rsd_data': rsd_data})

        else:
            if ios_version is not None and not is_major_version_17_or_greater(ios_version):
                rsd_data = (ios_version, udid)
                logger.info(f'RSD Data: {rsd_data}')
                lockdown = create_using_usbmux(udid, autopair=True)
                logger.info(f'Lockdown client = {lockdown}')
                rsd_host, rsd_port = rsd_data
                rsd_data_map.setdefault(udid, {})[connection_type] = {'host': rsd_host, 'port': rsd_port}
                
                return jsonify({'message': 'iOS version less than 17', 'rsd_data': rsd_data})

        return jsonify({'error': 'No iOS version present'})

    except Exception as e:
        logger.error(f'Error in connect_usb: {e}')
        return jsonify({'error': str(e)})
    finally:
        logger.warning('Connect Device function completed')


def connect_wifi(data):
    global rsd_data  # inserted
    global connection_type  # inserted
    global rsd_host  # inserted
    global ios_version  # inserted
    global lockdown  # inserted
    global udid  # inserted
    global rsd_port  # inserted
    
    try:
        logger.info(f'Wifi data: {data}')
        udid = data.get('udid', None)
        ios_version = data.get('ios_version')
        connection_type = data.get('connType')
        rsd_host = None
        rsd_port = None
        
        if ios_version is not None and is_major_version_17_or_greater(ios_version):
            logger.info('iOS 17+ detected')
            if version_check(ios_version):
                pass  # postinserted
            
            try:
                devices = get_wifi_with_retry()
                logger.info(f'Connect Wifi Devices: {devices}')
                logger.info(f'Wifi Address: {wifi_address}')
            except RuntimeError as e:
                error_message = str(e)
                logger.error(f'Error: {error_message}')
                return jsonify({'error': 'No Devices Found'})
            
            start_wifi_tunnel_thread()
            if not check_rsd_data():
                logger.error('RSD Data is None, Perhaps the tunnel isn\'t established')
            else:
                rsd_data = (rsd_host, rsd_port)
                logger.info(f'RSD Data: {rsd_data}')
                
            rsd_data_map.setdefault(udid, {})[connection_type] = {'host': rsd_host, 'port': rsd_port}
            logger.info(f'Device Connection Map: {rsd_data_map}')
            return jsonify({'rsd_data': rsd_data})

        else:
            if ios_version is not None and not is_major_version_17_or_greater(ios_version):
                rsd_data = (ios_version, udid)
                logger.info(f'RSD Data: {rsd_data}')
                lockdown = create_using_usbmux(udid, connection_type=connection_type, autopair=True)
                logger.info(f'Lockdown client = {lockdown}')
                rsd_data_map.setdefault(udid, {})[connection_type] = {'host': rsd_host, 'port': rsd_port}
                return jsonify({'message': 'iOS version less than 17', 'rsd_data': rsd_data})

        return jsonify({'error': 'No iOS version present'})

    except Exception as e:
        logger.error(f'Error in connect_wifi: {e}')
        return jsonify({'error': str(e)})
    
    finally:
        logger.warning('Connect Device function completed')

async def start_wifi_tcp_tunnel() -> None:
    global rsd_host  # inserted
    global rsd_port  # inserted
    logger.warning('Start Wifi TCP Tunnel')
    stop_remoted_if_required()
    lockdown = create_using_usbmux(udid)
    service = CoreDeviceTunnelProxy(lockdown)
    async with service.start_tcp_tunnel() as tunnel_result:
        resume_remoted_if_required()
        logger.info(f'Identifier: {service.remote_identifier}')
        logger.info(f'Interface: {tunnel_result.interface}')
        logger.info(f'RSD Address: {tunnel_result.address}')
        logger.info(f'RSD Port: {tunnel_result.port}')
        rsd_host = tunnel_result.address
        rsd_port = str(tunnel_result.port)
        while True:
            if terminate_tunnel_thread is True:
                return
            else:  # inserted
                await asyncio.sleep(0.5)

async def start_wifi_quic_tunnel() -> None:
    global rsd_host  # inserted
    global rsd_port  # inserted
    logger.warning('Start Wifi QUIC Tunnel')
    stop_remoted_if_required()
    service = await create_core_device_tunnel_service_using_remotepairing(udid, wifi_address, wifi_port)
    async with service.start_quic_tunnel() as tunnel_result:
        resume_remoted_if_required()
        logger.info(f'Identifier: {service.remote_identifier}')
        logger.info(f'Interface: {tunnel_result.interface}')
        logger.info(f'RSD Address: {tunnel_result.address}')
        logger.info(f'RSD Port: {tunnel_result.port}')
        rsd_host = tunnel_result.address
        rsd_port = str(tunnel_result.port)
        while True:
            if terminate_tunnel_thread is True:
                return
            else:  # inserted
                await asyncio.sleep(0.5)

def start_wifi_tunnel_thread():
    global terminate_tunnel_thread  # inserted
    terminate_tunnel_thread = False
    thread = threading.Thread(target=run_wifi_tunnel)
    thread.start()

def run_wifi_tunnel():
    try:
        if version_check(ios_version):
            asyncio.run(start_wifi_quic_tunnel())
        else:  # inserted
            asyncio.run(start_wifi_tcp_tunnel())
    except Exception as e:
        logger.error(f'Error in run_wifi_tunnel: {e}')

@app.route('/mount_developer_image', methods=['POST'])
def mount_developer_image():
    global lockdown  # inserted
    try:
        lockdown = create_using_usbmux(udid, autopair=True)
        logger.info(f'mount lockdown: {lockdown}')
        auto_mount(lockdown)
        return 'Developer image mounted successfully'
    except Exception as e:
        error_message = str(e)
        return jsonify({'error': error_message})

async def set_location_thread(latitude, longitude):
    global rsd_host  # inserted
    global rsd_port  # inserted
    try:
        if udid in rsd_data_map and connection_type in rsd_data_map[udid]:
            rsd_data = rsd_data_map[udid][connection_type]
            rsd_host = rsd_data['host']
            rsd_port = rsd_data['port']
            logger.info(f'RSD in udid mapping is: {rsd_data}')
            logger.info('RSD already created. Reusing connection')
            logger.info(f'RSD Data: {rsd_data}')

            if ios_version is not None and is_major_version_17_or_greater(ios_version):
                async with RemoteServiceDiscoveryService((rsd_host, rsd_port)) as sp_rsd:
                    with DvtSecureSocketProxyService(sp_rsd) as dvt:
                        LocationSimulation(dvt).set(latitude, longitude)
                        logger.warning('Location Set Successfully')
                        while not terminate_location_thread:
                            await asyncio.sleep(0.5)  # Use await for async sleep
            else:  # inserted
                if ios_version is not None and (not is_major_version_17_or_greater(ios_version)):
                    with DvtSecureSocketProxyService(lockdown=lockdown) as dvt:
                        LocationSimulation(dvt).clear()
                        LocationSimulation(dvt).set(latitude, longitude)
                        logger.warning('Location Set Successfully')
                        while not terminate_location_thread:
                            await asyncio.sleep(0.5)  # Use await for async sleep

        await asyncio.sleep(1)

    except asyncio.CancelledError:
        return None
    except ConnectionResetError as cre:
        if '[Errno 54] Connection reset by peer' in str(cre):
            logger.error('The Set Location buffer is full. Try to \'Stop Location\' to clear old connections')
    except Exception as e:
        logger.error(f'Error setting location: {e}')

def start_set_location_thread(latitude, longitude):
    global terminate_location_thread  # inserted
    stop_set_location_thread()
    terminate_location_thread = False

    async def run_async_function():
        await set_location_thread(latitude, longitude)

    def check_termination():
        while not terminate_location_thread:
            asyncio.run(asyncio.sleep(1))
        logger.info('Location Thread Terminated')
    location_thread = threading.Thread(target=lambda: asyncio.run(run_async_function()))
    location_thread.start()
    termination_thread = threading.Thread(target=check_termination)
    termination_thread.start()

def stop_set_location_thread():
    global terminate_location_thread  # inserted
    terminate_location_thread = True

@app.route('/set_location', methods=['POST'])
def set_location():
    try:
        if ios_version is not None:
            latitude, longitude = location.split()  # Ensure `location` is defined properly
            if is_major_version_17_or_greater(ios_version):
                start_set_location_thread(latitude, longitude)
            else:  # Handle iOS versions less than 17
                mount_developer_image()
                start_set_location_thread(latitude, longitude)
            return jsonify({'message': 'Location set successfully'})
        else:  # Case when no iOS version is present
            return jsonify({'error': 'No iOS version present'})
    except Exception as e:
        error_message = str(e)
        return jsonify({'error': error_message})


@app.route('/stop_location', methods=['POST'])
async def stop_location():
    global rsd_host  # inserted
    global rsd_port  # inserted
    global rsd_data  # inserted
    try:
        stop_set_location_thread()
        logger.info(f'stop set location data: {rsd_data}')
        
        if udid in rsd_data_map:
            if connection_type in rsd_data_map[udid]:
                rsd_data = rsd_data_map[udid][connection_type]
                rsd_host = rsd_data['host']
                rsd_port = rsd_data['port']

            if ios_version is not None:
                if is_major_version_17_or_greater(ios_version):
                    async with RemoteServiceDiscoveryService((rsd_host, rsd_port)) as sp_rsd:
                        with DvtSecureSocketProxyService(sp_rsd) as dvt:
                            LocationSimulation(dvt).clear()
                            logger.warning('Location Cleared Successfully')
                            return jsonify({'message': 'Location cleared successfully'})
                
                else:  # Handle iOS versions less than 17
                    with DvtSecureSocketProxyService(lockdown=lockdown) as dvt:
                        LocationSimulation(dvt).clear()
                        logger.warning('Location Cleared Successfully')
                        return jsonify({'message': 'Location cleared successfully'})

        return jsonify({'message': 'No UDID or connection type found'})
        
    except Exception as e:
        error_message = str(e)
        logger.error(f'Error in stop_location: {error_message}')
        return jsonify({'error': error_message})


def get_github_version():
    try:
        url = f'https://raw.githubusercontent.com/{GITHUB_REPO}/main/{CURRENT_VERSION_FILE}'
        response = requests.get(url)
        response.raise_for_status()
        github_version = response.text.strip()
        return github_version
    except requests.RequestException as e:
        return None

def get_github_broadcast():
    try:
        url = f'https://raw.githubusercontent.com/{GITHUB_REPO}/main/{BROADCAST_FILE}'
        response = requests.get(url)
        response.raise_for_status()
        github_broadcast = response.text.strip()
        return github_broadcast
    except requests.RequestException as e:
        return None

def remove_ansi_escape_codes(text):
    ansi_escape = re.compile('\\x1b[^m]*m')
    return ansi_escape.sub('', text)

async def get_network_devices():
    async for ip, lockdown in get_mobdev2_lockdowns():
        print(ip, lockdown.short_info)

@app.route('/list_devices')
def py_list_devices():
    try:
        connected_devices = {}
        all_devices = list_devices()
        logger.info(f'\n\nRaw Devices:  {all_devices}\n')
        for device in all_devices:
            udid = device.serial
            connection_type = device.connection_type
            lockdown = create_using_usbmux(udid, connection_type=connection_type, autopair=True)
            info = lockdown.short_info
            wifi_connection_state = lockdown.enable_wifi_connections
            if wifi_connection_state == False:
                logger.info('Enabling Wifi Connections')
                wifi_connection_state = lockdown.enable_wifi_connections = True
                logger.info('Wifi Connection State: True')
            info['wifiState'] = wifi_connection_state
            info['userLocale'] = get_user_country()
            if connection_type == 'Network':
                connection_type = 'Wifi'
            if udid in connected_devices:
                if connection_type in connected_devices[udid]:
                    connected_devices[udid][connection_type].append(info)
                else:  # inserted
                    connected_devices[udid][connection_type] = [info]
            else:  # inserted
                connected_devices[udid] = {connection_type: [info]}
        logger.info(f'\n\nConnected Devices: {connected_devices}\n')
        if current_platform == 'darwin' and os.geteuid()!= 0:
            logger.error('*********************** WARNING ***********************')
            logger.error('Not running as Sudo, this probably isn\'t going to work')
            logger.error('*********************** WARNING ***********************')
        return jsonify(connected_devices)
    except ConnectionAbortedError as e:
        logger.error(f'ConnectionAbortedError occurred: {e}')
        return {'error'}
    except Exception as e:
        error_message = str(e)
        return jsonify({'error': error_message})

def clear_geoport():
    logger.info('clear any GeoPort instances')
    substring = 'GeoPort'
    for process in psutil.process_iter(['pid', 'name']):
        if substring in process.info['name']:
            logger.info(f"Found process: {process.info['pid']} - {process.info['name']}")
            process.terminate()
    logger.warning('No GeoPort found')

def clear_old_geoport():
    logger.info('clear old GeoPort instances')
    substring = 'GeoPort'
    current_pid = os.getpid()
    for process in psutil.process_iter(['pid', 'name']):
        if substring in process.info['name'] and process.info['pid']!= current_pid:
            logger.info(f"Found process: {process.info['pid']} - {process.info['name']}")
            process.terminate()

def shutdown_server():
    logger.warning('shutdown server')
    asyncio.run(stop_location())
    stop_set_location_thread()
    stop_tunnel_thread()
    cancel_async_tasks()
    terminate_threads()
    clear_geoport()
    logger.error('OS Kill')
    os.kill(os.getpid(), signal.SIGINT)
    list_threads()
    terminate_threads()
    logger.error('sys exit')
    os._exit(0)

def terminate_threads():
    """\n    Terminate all threads.\n    """  # inserted
    for thread in threading.enumerate():
        if thread!= threading.main_thread():
            logger.info(f'thread: {thread}')
            terminate_flag = threading.Event()
            terminate_flag.set()

def list_threads():
    """\n    Terminate all threads.\n    """  # inserted
    for thread in threading.enumerate():
        logger.info(f'thread: {thread}')

def cancel_async_tasks():
    try:
        tasks = asyncio.all_tasks()
        for task in tasks:
            logger.info(f'task: {task}')
            task.cancel()
    except RuntimeError as e:
        if 'no running event loop' in str(e):
            logger.error('No running event loop found.')
        else:  # inserted
            raise e

@app.route('/exit', methods=['POST'])
def exit_app():
    logger.warning('Exit GeoPort')
    shutdown_server()
    response = {'success': True, 'message': 'Server is shutting down...'}
    return jsonify(response)

@app.route('/')
def index():
    fetch_api_data(api_url)
    github_version = get_github_version()
    github_broadcast = get_github_broadcast()
    user_locale = get_user_country()
    logger.info(f'Country: {user_locale}')
    logger.info(f'Current platform: {platform}')
    logger.info(f'App Version = {APP_VERSION_NUMBER}')
    logger.info(f'base dir =  {base_directory}')
    logger.info(f'GitHub Version = {github_version}')
    if github_version and github_version > APP_VERSION_NUMBER:
        version_message = f'Update available. New Version is {github_version}'
    else:  # inserted
        if github_version and github_version < APP_VERSION_NUMBER:
            version_message = f'Beta Testing. App version is {APP_VERSION_NUMBER} - github is {github_version}'
        else:  # inserted
            version_message = None
    return render_template('map.html', version_message=version_message, github_broadcast=github_broadcast, user_locale=user_locale, app_version_num=APP_VERSION_NUMBER, app_version_type=APP_VERSION_TYPE, error_message=error_message, current_platform=platform, sudo_message=sudo_message)

def open_browser():
    time.sleep(2)
    browser = webbrowser.get()
    browser.open(f'http://localhost:{chosen_port}')

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def try_bind_listener_on_free_port():
    global chosen_port  # inserted
    min_port = 49215
    max_port = 65535
    if args.port:
        chosen_port = args.port
    else:  # inserted
        chosen_port = flask_port
    if is_port_in_use(chosen_port):
        chosen_port = random.randint(min_port, max_port)
    logger.info(f'Serving: http://localhost:{chosen_port}')
    return chosen_port
if __name__ == '__main__':
    if is_windows:
        try:
            import pyi_splash
            pyi_splash.update_text('UI Loaded ...')
            logger.info('clear splash')
            pyi_splash.close()
        except:
            pass
        if not pyuac.isUserAdmin():
            print('Relaunching as Admin')
            pyuac.runAsAdmin()
    chosen_port = try_bind_listener_on_free_port()
    if not args.no_browser:
        open_browser()
    else:  # inserted
        logger.info('--no-browser flag passed')
        logger.info('Running without auto-browser popup')
    app.run(debug=False, use_reloader=False, port=chosen_port, host='0.0.0.0')