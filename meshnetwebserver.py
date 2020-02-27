from webserver import *
from uthread import *
import network
import socket
from time import sleep
import sys

class MeshNetWebServer(thread):
    def __init__(self, config, name="MeshNetWebServer", apmode=True, display=None):
        super().__init__(name, stack=8192)
        self._config = config
        self._apmode = apmode
        self._display = display if display else lambda text : None

        self._wlan = None

    # Loop to run server in apmode or host
    def run(self):
        rc = 0
        while rc == 0 and self.running:
            if (    self._apmode and self.create_accesspoint(self._config.get('apmode'))) or \
               (not self._apmode and self.connect_to_accesspoint(self._config.get('host.ap'))):

                self._display("Web start",  clear=False, line=5)

                # Created network connection
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('', 80))

                # Terminate server if running drops
                server = WebServer(term_request = lambda : not self.running)

                self._display("Web running", clear = False, line=5)

                server.run(s,
                           page_data={
                               '/': self.home_page,
                               '/config': self.config_page,
                               '/reboot': self.reboot_page,
                               # Default for invalid page reference
                               None: self.not_found_page,
                           })
                    
                s.close()

                self.disconnect()
                seld._display("Web stopped", clear=False, line=5)
            else:
                self._display("Web failed", clear=False, line=5)
                rc = -1

        return rc

    def connect_to_accesspoint(self, config):
        try:
            self._wlan = network.WLAN(network.STA_IF)

            # print("connect_to_accesspoint '%s'" % (config))
            # Connect to lan
            self._wlan.active(True)
            self._wlan.connect(config['essid'], config['password'])
            # print("connect_to_accesspoint with %s %s" % (config['essid'], config['password']))
    
            # Wait until connected or 30 second timeout
            # Cannot use lightsleep as it kills the network
            timer = utime.time() + 30
            while not self._wlan.isconnected() and utime.time() < timer:
                pass
    
            if self._wlan.isconnected():
                # print("connect_to_accesspoint: %s" % (str(self._wlan.ifconfig())))
                self._display("%s" % self._wlan.ifconfig()[0], clear=False)
            else:
                self.disconnect()

        except Exception as e:
            sys.print_exception(e)
            self.disconnect()

        return self._wlan != None

    def disconnect(self):
        if self._wlan:
            try:
                self._wlan.disconnect()
            except:
                pass
            finally:
                self._wlan.active(False)

            self._wlan = None

    def create_accesspoint(self, config):

        try:
            self._wlan = network.WLAN(network.AP_IF)
            self._wlan.active(True)

            essid = config['essid']
            password = config['password']
            if password != "":
                self._wlan.config(essid=essid, authmode=network.AUTH_WPA_WPA2_PSK, password=password)
            else:
                self._wlan.config(essid=essid)

            print("create_accesspoint: %s" % str(self._wlan.ifconfig()))
            self._display("%s" % self._wlan.ifconfig()[0], clear=False)

        except Exception as e:
            sys.print_exception(e)
            self.disconnect()

        return self._wlan != None

    def home_page(self, request=None, notice=None):
        if request is None or request.method == "GET":
            # Create simple webserver access
            header = build_header("200 OK", "text/html")
    
            html = open("html/index.html").read().format(device=self._config.get("device.name"), notice="<h2>"+notice+"</h2>" if notice else "",)
    
        else:
            header, html = self.home_page(notice="Invalid type: %s" % request.method)
    
        return header, html
    
    def not_found_page(self, request=None, notice=None):
        return build_header("404 Not Found", "text/html"), open("html/not_found.html").read()

    def config_page(self, request=None, notice=None):
        if request is None or request.method == "GET":
            var_list = self._config.list()
    
            # Sort them
            var_list.sort()
    
            rows = []
            for var in var_list:
                value = self._config.get(var)
                try:
                    # print("trying options")
                    # Split var into subvars and final var
                    subvar, endvar = var.rsplit('.', 1)
                    # print("Looking at %s.%%%s%%options" % (subvar, endvar))
                    selector = self._config.get("%s.%%%s%%options" % (subvar, endvar))
                    # print("selector is %s (%s)" % (selector, type(selector)))
                    # Selector with option list
                    rows.append("<tr><td>%s</td><td><select name='%s'>" % (var, var))
                    for option in selector:
                        if option == value:
                            rows.append("  <option value='%s' selected=selected>%s</option>" % (option, option))
                        else:
                            rows.append("  <option value='%s'>%s</option>" % (option, option))
                    rows.append("</select></td></tr>")

                except Exception as e:
                    # sys.print_exception(e)
                    # Simple table data entry
                    rows.append("<tr><td>%s</td><td><input name='%s' value='%s'/></td></tr>" % (var, var, value))
    
            header = build_header("200 OK", "text/html")
            html = open("html/config.html").read().format( device=self._config.get("device.name"), table='\n'.join(rows), notice="<h2>"+notice+"</h2>" if notice else "",)
    
        elif request.method == 'POST':
    
            response = request.post_response()
    
            help(response)

            try:
                # Put the results into the persistent data field
                for item in response:
                    # print("config_page: processing '%s'" % item)
                    name, value = item.split('=', 1)
                    self._config.set(name, value)
    
                self._config.flush()
                notice = "Configuration updated"
    
            except Exception as e:
                sys.print_exception(e)
                notice = str(e)
    
            header, html = self.config_page(notice=notice)
    
        else:
            header, html = self.config_page(notice="Invalid type: %s" % request.method)
    
        return header, html

    def reboot_page(self, request=None, notice=None):
        if request is None or request.method == "GET":

            header = build_header("200 OK", "text/html")
            html = open("html/reboot.html").read().format(device=self._config.get("device.name"), notice="<h2>"+notice+"</h2>" if notice else "",)
    
        elif request.method == 'POST':
            header, html = self.home_page(notice="Rebooting")
            
            # Set a thread to do a reboot after five seconds
            thread(run=self.reboot_delay).start()

        else:
            header, html = self.reboot_page(notice="Invalid type: %s" % request.method)
    
        return header, html

    def reboot_delay(self, t):
        sleep(1)
        import machine
        machine.reset()

        
