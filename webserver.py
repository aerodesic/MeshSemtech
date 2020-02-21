import utime
from errno import ETIMEDOUT
import sys
import ure as re
import gc
from uthread import *

def build_header(error, content_type):
    return "\n".join([
        "HTTP/1.1 %s" % error,
        "Content-Type: %s" % content_type,
    ]) + "\n"
    
    
def urldecode(str):
    dic = {
        "+": " ",
        "%21":"!",
        "%22":'"',
        "%23":"#",
        "%24":"$",
        "%26":"&",
        "%27":"'",
        "%28":"(",
        "%29":")",
        "%2A":"*",
        "%2B":"+",
        "%2C":",",
        "%2F":"/",
        "%3A":":",
        "%3B":";",
        "%3D":"=",
        "%3F":"?",
        "%40":"@",
        "%5B":"[",
        "%5D":"]",
        "%7B":"{",
        "%7D":"}",
    }

    for k,v in dic.items():
        str=str.replace(k,v)

    return str

class HttpRequest:
    def __init__(self, headers=None, body=None):
        self.headers = headers if headers != None else []
        self.body = body if body != None else ''

    def get_method(self):
        if len(self.headers) != 0:
            line0 = self.headers[0].split(b' ')
            method = line0[0].decode('utf-8').strip()
        else:
            method = "GET"

        return method

    def get_url(self):
        if len(self.headers) != 0:
            line0 = self.headers[0].split(b' ')
            url    = line0[1].decode('utf-8').strip()
        else:
            url = "/"
        return url

    method = property(get_method)
    url = property(get_url)

    def add_header(self, header):
        # print("add_header: %s" % header)
        self.headers.append(header)

    def set_body(self, body):
        self.body = None
        gc.collect()
        self.body = body

    def post_response(self):
        eol=self.body.find(b'\r\n')
        line0 = self.body[0:eol if eol >= 0 else None]
        # print("post_response: line0 '%s'" % line0)
        return [ urldecode(x) for x in line0.decode('utf-8').split('&') ]

    def find_header_matching(self, search_string, index = 0):
        if isinstance(search_string, str):
            search_string = bytes(search_string, 'utf-8')

        while index < len(self.headers):
            # print("find_item_containing: '%s' in '%s'" % (search_string, string_list[index]))
            if re.match(search_string, self.headers[index]):
                return index
            else:
                index = index + 1

        # No match found
        return None
    
    def body_line_at(self, index):
        eol = self.body.find(b'\r\n', index)
        if eol < 0:
            line = self.body[index:]
        else:
            line = self.body[index:eol]

        return line, eol

    def find_body_matching(self, search_string, index = 0):
        if isinstance(search_string, str):
            search_string = bytes(search_string, 'utf-8')

        eol = 0
        while eol >= 0:
            # print("find_body_matching: %s at %d" % (search_string, index))
            line, eol = self.body_line_at(index)

            if re.match(search_string, line):
                return index
            elif eol >= 0:
                index = eol + 2

        # No match found
        return None

    #
    #
    # Search a matching tag=<value> in header and return value
    # Must include the delimiter (: or =) after the tagname in the call.
    #
    def get_header_tag_value(self, tag_name, index = 0):
        if isinstance(tag_name, str):
            tag_name = bytes(tag_name, 'utf-8')

        # Try with bounding quotes first
        p = re.search(b'^.*\b?%s"([^"]*)"' % (tag_name), self.headers[index])
        if not p:
            # Go to closing EOL
            p = re.search(b'^.*\b?%s([^$]*)' % (tag_name), self.headers[index])

        return p.group(1) if p else None
    #
    #
    # Search a matching tag=<value> in header and return value
    # Must include the delimiter (: or =) after the tagname in the call.
    #
    def get_body_tag_value(self, tag_name, index = 0):
        if isinstance(tag_name, str):
            tag_name = bytes(tag_name, 'utf-8')

        # Try with bounding quotes first
        line, dummy = self.body_line_at(index)
        p = re.search(b'^.*\b?%s"([^"]*)"' % (tag_name), line)
        if not p:
            # Go to closing CR or LF or EOL
            p = re.search(b'^.*\b?%s([^$^\r^\n]*)' % (tag_name), line)

        return p.group(1) if p else None
    

class WebServer():
    def __init__(self, term_request=lambda : False):
        self._term_request = term_request

    def run(self, s, page_data, runtimeout=0, listentimeout=1):
        timer = utime.time() + runtimeout

        while not self._term_request() and (runtimeout == 0 or utime.time() < timer):
            try:
                s.settimeout(listentimeout)
                s.listen(1) 
                conn, addr = s.accept()
                print("Connection from %s" % str(addr))
                # Restart timer
                timer = utime.time() + runtimeout
        
            except OSError as e:
                if e.args[0] != ETIMEDOUT:
                    sys.print_exception(e)
                else:
                    pass
                       
            except Exception as e:
                sys.print_exception(e)
        
            except:
                raise
        
            else:
                try:
                    request = HttpRequest()
    
                    # print("Starting to read headers:")
                    # Read the headers
    
                    header = conn.readline().strip(b'\r\n')
                    while header != b'':
                        request.add_header(header)
                        header = conn.readline().strip(b'\r\n')
    
                    length_index = request.find_header_matching(b"^Content-Length:.*")
                    if length_index != None:
                        body_size = request.get_header_tag_value(b"Content-Length:", length_index)
                    else:
                        length_index = request.find_header_matching(b"^Transfer-Encoding:.*")
                        if length_index != None:
                            body_size = request.get_header_tag_value(b"Transfer-Encoding:", length_index)
                        else:
                            body_size = 0
    
                    body_size = int(body_size)
    
                    if body_size > 0:
                        # print("Reading body of %d bytes" % body_size)
                        gc.collect()
                        body = conn.read(body_size)
                        # print("len of body is %d body_size %d" % (len(body), body_size))
                        request.set_body(body)
                        # print("Body read: %s" % body)
    
                except Exception as e:
                    print("Exception %s" % e)
                    sys.print_exception(e)
                    request = HttpRequest()
    
                # print("request url '%s' method '%s'" % (request.url, request.method))
    
                if request.url in page_data:
                    header, html = page_data[request.url](request)
    
                else:
                    # Page not found
                    header, html = page_data[None](request)
    
                try:
                    # print("header:%d" % len(header))
                    # print(header)
                    conn.sendall(header)
                    conn.sendall("\r\n")
                    # print("html:%d" % len(html))
                    # print(html)
                    conn.sendall(html)
    
                except Exception as e:
                    sys.print_exception(e)
    
                finally:
                    conn.close()
    
                utime.sleep(1)

