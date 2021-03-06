from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.protocol import Protocol, Factory

from fcgiproto import FastCGIConnection, RequestBeginEvent, RequestDataEvent


class FastCGIProtocol(Protocol):
    def __init__(self):
        self.conn = FastCGIConnection()
        self.requests = {}

    def dataReceived(self, data):
        try:
            for event in self.conn.feed_data(data):
                if isinstance(event, RequestBeginEvent):
                    self.requests[event.request_id] = (
                        event.params, event.keep_connection, bytearray())
                elif isinstance(event, RequestDataEvent):
                    request_data = self.requests[event.request_id][2]
                    if event.data:
                        request_data.extend(event.data)
                    else:
                        params, keep_connection, request_data = self.requests.pop(event.request_id)
                        self.handle_request(event.request_id, params, request_data)
                        if not keep_connection:
                            self.transport.loseConnection()

            self.transport.write(self.conn.data_to_send())
        except Exception:
            self.transport.abortConnection()
            raise

    def handle_request(self, request_id, params, content):
        fcgi_params = '\n'.join('<tr><td>%s</td><td>%s</td></tr>' % (key, value)
                                for key, value in params.items())
        content = content.decode('utf-8', errors='replace')
        response = ("""\
<!DOCTYPE html>
<html>
<body>
<h2>FCGI parameters</h2>
<table>
%s
</table>
<h2>Request body</h2>
<pre>%s</pre>
</body>
</html>
""" % (fcgi_params, content)).encode('utf-8')
        headers = [
            (b'Content-Length', str(len(response)).encode('ascii')),
            (b'Content-Type', b'text/html; charset=UTF-8')
        ]
        self.conn.send_headers(request_id, headers, 200)
        self.conn.send_data(request_id, response, end_request=True)


class FastCGIFactory(Factory):
    def buildProtocol(self, addr):
        return FastCGIProtocol()


endpoint = TCP4ServerEndpoint(reactor, 9500)
endpoint.listen(FastCGIFactory())

try:
    reactor.run()
except (KeyboardInterrupt, SystemExit):
    pass
