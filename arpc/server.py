#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio

from .dispatcher import Dispatcher
from .protocols import Protocol
from .transports import ServerTransport


class Server:
    """High level RPC server.

    :param transport: The :py:class:`~tinyrpc.transports.RPCTransport` to use.
    :param protocol: The :py:class:`~tinyrpc.RPCProtocol` to use.
    :param dispatcher: The :py:class:`~tinyrpc.dispatch.RPCDispatcher` to use.
    """

    trace = None
    """Trace incoming and outgoing messages.

    When this attribute is set to a callable(or awaitable) this callable will be called directly
    after a message has been received and immediately after a reply is sent.
    The callable should accept three positional parameters:
    * *direction*: string, either '-->' for incoming or '<--' for outgoing data.
    * *context*: the context returned by :py:meth:`~tinyrpc.transport.RPCTransport.receive_message`.
    * *message*: the message string itself.

    Example::

        def my_trace(direction, context, message):
            logger.debug('%s%s', direction, message)

        server = RPCServer(transport, protocol, dispatcher)
        server.trace = my_trace
        server.serve_forever()

    will log all incoming and outgoing traffic of the RPC service.
    """

    def __init__(self, protocol: Protocol, transport: ServerTransport, dispatcher: Dispatcher):
        self.protocol = protocol
        self.transport = transport
        self.dispatcher = dispatcher
        self.trace = None

    async def start(self):
        await self.transport.start(self)

    async def stop(self):
        await self.transport.stop()

    async def handler(self, message):
        """Handle a single request.

        Polls the transport for a new message.

        After a new message has arrived :py:meth:`_spawn` is called with a handler
        function and arguments to handle the request.

        The handler function will try to decode the message using the supplied
        protocol, if that fails, an error response will be sent. After decoding
        the message, the dispatcher will be asked to handle the resultung
        request and the return value (either an error or a result) will be sent
        back to the client using the transport.
        """

        # FIXME: rewrite this code
        if asyncio.iscoroutine(self.trace):
            await self.trace('-->', message)
        elif callable(self.trace):
            self.trace('-->', message)

        request = None

        try:
            request = self.protocol.parse_request(message)
            response = await self.dispatcher.dispatch(request)
        except Exception as e:
            response = self.protocol.create_error_response(e, request)

        # send reply
        if response is not None:
            result = response.serialize()

            # FIXME: rewrite this code
            if asyncio.iscoroutine(self.trace):
                await self.trace('-->', result)
            elif callable(self.trace):
                self.trace('-->', result)

            return result
