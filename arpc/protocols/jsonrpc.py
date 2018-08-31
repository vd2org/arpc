#!/usr/bin/env python
# -*- coding: utf-8 -*-

import typing

from .. import Protocol, Serializer


class JSONRPCProtocol(Protocol):
    """JSONRPC version 2.0 protocol implementation."""

    JSON_RPC_VERSION = "2.0"
    _ALLOWED_REPLY_KEYS = sorted(['id', 'jsonrpc', 'error', 'result'])
    _ALLOWED_REQUEST_KEYS = sorted(['id', 'jsonrpc', 'method', 'params'])

    class SuccessResponse(Protocol.SuccessResponse):
        def __init__(self, serializer: Serializer, uid: int, result: typing.Any):
            self._serializer = serializer
            self.uid = uid
            self.result = result

        def serialize(self):
            self._serializer.serialize({
                'jsonrpc': JSONRPCProtocol.JSON_RPC_VERSION,
                'id': self.uid,
                'result': self.result
            })

    class ErrorResponse(Protocol.ErrorResponse):
        def __init__(self, serializer: Serializer, code: int, message: str, uid: typing.Optional[int] = None, data: typing.Any = None):
            self._serializer = serializer
            self.code = code
            self.message = message
            self.uid = uid
            self.data = data

        def to_exception(self):
            class ParseError(Protocol.Error):
                def __init__(self, message: str = "Parse error."):
                    super().__init__(-32700, message)

            class InvalidRequestError(Protocol.Error):
                def __init__(self, message: str = "Invalid Request"):
                    super().__init__(-32600, message)

            class MethodNotFoundError(Protocol.Error):
                def __init__(self, message: str = "Method not found"):
                    super().__init__(-32601, message)

            class InvalidParamsError(Protocol.Error):
                def __init__(self, message: str = "Invalid params"):
                    super().__init__(-32602, message)

            class InternalError(Protocol.Error):
                def __init__(self, message: str = "Internal error"):
                    super().__init__(-32603, message)

            class InvalidReplyError(Protocol.Error):
                def __init__(self, message: str = "Invalid reply"):
                    super().__init__(-32001, message)

        def serialize(self):
            msg = {
                'jsonrpc': JSONRPCProtocol.JSON_RPC_VERSION,
                'id': self.uid,
                'error': {
                    'code': self.code,
                    'message': str(self.message),
                }
            }
            if hasattr(self, 'data'):
                msg['error']['data'] = self.data

            return self._serializer.serialize(msg)

    class Request(Protocol.Request):
        def __init__(self, serializer: Serializer, method: str, uid: typing.Optional[int] = None, args: typing.Optional[list] = None,
                     kwargs: typing.Optional[dict] = None):

            if args and kwargs:
                raise JSONRPCProtocol.InvalidRequestError('Does not support args and kwargs at the same time.')
            self._serializer = serializer
            self.method = method
            self.uid = uid
            self.args = args
            self.kwargs = kwargs

        def serialize(self):
            msg = {
                'jsonrpc': JSONRPCProtocol.JSON_RPC_VERSION,
                'method': self.method,
            }
            if self.args:
                msg['params'] = self.args
            if self.kwargs:
                msg['params'] = self.kwargs
            if self.uid is not None:
                msg['id'] = self.uid

            return self._serializer.serialize(msg)

    class ParseError(Protocol.Error):
        def __init__(self, message: str = "Parse error."):
            super().__init__(-32700, message)

    class InvalidRequestError(Protocol.Error):
        def __init__(self, message: str = "Invalid Request"):
            super().__init__(-32600, message)

    class MethodNotFoundError(Protocol.Error):
        def __init__(self, message: str = "Method not found"):
            super().__init__(-32601, message)

    class InvalidParamsError(Protocol.Error):
        def __init__(self, message: str = "Invalid params"):
            super().__init__(-32602, message)

    class InternalError(Protocol.Error):
        def __init__(self, message: str = "Internal error"):
            super().__init__(-32603, message)

    class InvalidReplyError(Protocol.Error):
        def __init__(self, message: str = "Invalid reply"):
            super().__init__(-32001, message)

    def __init__(self, serializer: Serializer, counter: int = 0):
        """Creates new protocol object.

        :type counter: start request id counter value
        """
        self._serializer = serializer
        self._counter = counter

    def _get_uid(self):
        self._counter += 1
        return self._counter

    def create_request(self, method: str, args: list = None, kwargs: dict = None,
                       one_way: bool = False) -> Request:

        if args and kwargs:
            raise self.InvalidRequestError('Does not support args and kwargs at the same time.')

        uid = None if one_way else self._get_uid()

        return self.Request(self._serializer, method, uid, args, kwargs)

    def create_response(self, request: Request, reply: typing.Any) -> SuccessResponse:
        return self.SuccessResponse(self._serializer, request.uid, reply)

    def create_error_response(self, exc: Exception,
                              request: Request = None) -> ErrorResponse:
        e = self.InternalError() if isinstance(exc, self.Error) else self.InternalError()
        uid = request.uid if request else None
        return self.ErrorResponse(self._serializer, e.code, e.message, uid, e.data)

    def parse_request(self, data: bytes) -> Request:
        try:
            req = json.loads(data)
        except Exception as e:
            raise self.ParseError()

        for k in req.keys():
            if k not in self._ALLOWED_REQUEST_KEYS:
                raise self.InvalidRequestError('Key not allowed: %s' % k)

        if req.get('jsonrpc') != self.JSON_RPC_VERSION:
            raise self.InvalidRequestError("Wrong or missing jsonrpc version")

        method = req['method']
        if not isinstance(method, str):
            raise self.InvalidRequestError("method must be str")

        uid = req.get('id')
        if uid and not isinstance(uid, int):
            raise self.InvalidRequestError("id must be int")

        params = req.get('params')
        args = None
        kwargs = None
        if params != None:
            if isinstance(params, list):
                args = params
            elif isinstance(params, dict):
                kwargs = params
            else:
                raise self.InvalidParamsError("params must be list or dict")

        return self.Request(self._serializer, method, uid, args, kwargs)

    def parse_response(self, data: bytes) -> typing.Union[SuccessResponse, ErrorResponse]:
        try:
            rep = self._serializer.deserialize(data)
        except Exception as e:
            raise self.InvalidReplyError()

        for k in rep.keys():
            if k not in self._ALLOWED_REPLY_KEYS:
                raise self.InvalidReplyError('Key not allowed: %s' % k)

        if rep.get('jsonrpc') != self.JSON_RPC_VERSION:
            raise self.InvalidReplyError("Wrong or missing jsonrpc version")

        uid = rep.get('id')
        if uid and not isinstance(uid, int):
            raise self.InvalidReplyError("id must be int")

        if ('error' in rep) == ('result' in rep):
            raise self.InvalidReplyError('Reply must contain exactly one of result and error.')

        if 'result' in rep:
            return self.SuccessResponse(self._serializer, uid, rep['result'])
        else:
            error = rep['error']

            code = error.get('code')
            if not isinstance(code, int):
                raise self.InvalidReplyError("error.code must be int")

            message = error.get('code')
            if message and not isinstance(message, str):
                raise self.InvalidReplyError("error.message must be str")

            data = error.get('data')

            return self.ErrorResponse(self._serializer, code, message, uid, data)
