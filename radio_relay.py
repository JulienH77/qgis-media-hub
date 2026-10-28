# -*- coding: utf-8 -*-
"""Relais audio sur localhost utilisant QgsNetworkAccessManager.

Le mode reseau QGIS peut utiliser la configuration proxy du poste, mais ne
contourne pas les restrictions du reseau. Les redirections HTTP 301/302/303/
307/308 sont suivies explicitement (Qt 5 utilise parfois la politique manuelle).
"""

import secrets
from urllib.parse import urlsplit

from qgis.PyQt.QtCore import QObject, QTimer, QUrl, pyqtSignal
from qgis.PyQt.QtNetwork import (
    QHostAddress, QNetworkReply, QNetworkRequest, QTcpServer
)


MAX_REDIRECTS = 7
REDIRECT_CODES = (301, 302, 303, 307, 308)


def safe_destination(current, target, visited, max_redirects=MAX_REDIRECTS):
    """Valide une redirection sans changement HTTPS -> HTTP ni boucle infinie.

    Les URL sont des valeurs fournies par le serveur (pas du code execute).
    La fonction est volontairement pure pour etre testable hors de QGIS.
    """
    from urllib.parse import urljoin
    if len(visited) >= max_redirects + 1:
        raise ValueError('Trop de redirections successives (maximum {}).'.format(max_redirects))
    if not target:
        raise ValueError('Redirection du serveur sans adresse de destination (Location).')
    destination = urljoin(current, target)
    origin = urlsplit(current)
    new = urlsplit(destination)
    if new.scheme.lower() not in ('http', 'https') or not new.hostname:
        raise ValueError('Redirection vers une adresse non HTTP(S).')
    if origin.scheme.lower() == 'https' and new.scheme.lower() != 'https':
        raise ValueError('Redirection HTTPS vers HTTP non securisee.')
    if destination in visited:
        raise ValueError('Boucle de redirection detectee.')
    return destination


class QgisRadioRelay(QObject):
    failed = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        from qgis.core import QgsNetworkAccessManager
        self.manager = QgsNetworkAccessManager.instance()
        self.server = QTcpServer(self)
        if not self.server.listen(QHostAddress.LocalHost, 0):
            raise RuntimeError('Impossible de creer le relais local (127.0.0.1).')
        self.server.newConnection.connect(self._incoming)
        self.source = ''
        self.token = secrets.token_urlsafe(24)
        self.socket = None
        self.reply = None
        self._header_sent = False
        self._has_data = False
        self._generation = 0
        self._visited = set()
        self._redirect_count = 0
        self._request_buffer = bytearray()

    def url_for(self, source):
        if not source.lower().startswith(('https://', 'http://')):
            raise ValueError('Le relais accepte uniquement les flux HTTP(S).')
        self._cancel_active()
        self.source = source
        self.token = secrets.token_urlsafe(24)
        return 'http://127.0.0.1:{}/{}'.format(self.server.serverPort(), self.token)

    def _incoming(self):
        while self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            if self.socket is not None:
                sock.write(b'HTTP/1.1 503 Busy\r\nConnection: close\r\n\r\n')
                sock.disconnectFromHost()
                continue
            self.socket = sock
            self._header_sent = False
            self._has_data = False
            self._visited = set()
            self._redirect_count = 0
            self._request_buffer = bytearray()
            generation = self._generation
            sock.readyRead.connect(lambda s=sock, g=generation: self._handle_request(s, g))
            sock.disconnected.connect(lambda s=sock, g=generation: self._disconnected(s, g))
            if sock.bytesAvailable():
                self._handle_request(sock, generation)

    def _handle_request(self, sock, generation):
        if sock is not self.socket or generation != self._generation or self.reply is not None:
            return
        self._request_buffer.extend(bytes(sock.read(8192)))
        if len(self._request_buffer) > 8192:
            sock.write(b'HTTP/1.1 431 Request Header Fields Too Large\r\nConnection: close\r\n\r\n')
            sock.disconnectFromHost()
            return
        if b'\r\n' not in self._request_buffer:
            return
        request_line = bytes(self._request_buffer).split(b'\r\n', 1)[0]
        expected = ('GET /' + self.token + ' ').encode('ascii')
        head = ('HEAD /' + self.token + ' ').encode('ascii')
        if request_line.startswith(head):
            sock.write(b'HTTP/1.1 200 OK\r\nContent-Type: audio/mpeg\r\nConnection: close\r\n\r\n')
            sock.disconnectFromHost()
            return
        if not request_line.startswith(expected):
            sock.write(b'HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n')
            sock.disconnectFromHost()
            return
        self._visited = {self.source}
        self._issue_request(self.source, generation)

    def _issue_request(self, url, generation):
        if self.socket is None or generation != self._generation:
            return
        outgoing = QNetworkRequest(QUrl(url))
        outgoing.setRawHeader(b'User-Agent', b'Mozilla/5.0 (compatible; QGIS-Media-Hub/1.3)')
        outgoing.setRawHeader(b'Accept', b'audio/*,application/octet-stream,*/*')
        outgoing.setRawHeader(b'Accept-Encoding', b'identity')
        outgoing.setRawHeader(b'Icy-MetaData', b'0')
        # Important : les redirections sont gerees ici, explicitement.
        # On ne suppose pas que le NetworkAccessManager QGIS les suit.
        if hasattr(QNetworkRequest, 'RedirectPolicyAttribute'):
            outgoing.setAttribute(QNetworkRequest.RedirectPolicyAttribute,
                                  QNetworkRequest.ManualRedirectPolicy)
        elif hasattr(QNetworkRequest, 'FollowRedirectsAttribute'):
            outgoing.setAttribute(QNetworkRequest.FollowRedirectsAttribute, False)
        reply = self.manager.get(outgoing)
        self.reply = reply
        try:
            reply.setReadBufferSize(256 * 1024)
        except AttributeError:
            pass
        reply.metaDataChanged.connect(lambda r=reply, g=generation: self._metadata(r, g))
        reply.readyRead.connect(lambda r=reply, g=generation: self._available(r, g))
        reply.finished.connect(lambda r=reply, g=generation: self._finished(r, g))
        QTimer.singleShot(16000, lambda r=reply, g=generation: self._timeout(r, g))

    def _valid(self, reply, generation):
        return generation == self._generation and reply is self.reply and self.socket is not None

    @staticmethod
    def _status(reply):
        value = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _follow_redirect(self, reply, generation):
        if not self._valid(reply, generation):
            return
        target = reply.attribute(QNetworkRequest.RedirectionTargetAttribute)
        target_text = target.toString() if target is not None and not target.isEmpty() else ''
        if not target_text:
            target_text = bytes(reply.rawHeader(b'Location')).decode('utf-8', 'replace').strip()
        try:
            original = reply.url().toString()
            destination = safe_destination(original, target_text, self._visited)
        except ValueError as exc:
            self._failure('HTTP {} : {}'.format(self._status(reply), exc))
            return
        self._redirect_count += 1
        self._visited.add(destination)
        final_host = urlsplit(destination).hostname or 'serveur inconnu'
        self.progress.emit('Redirection HTTP {} suivie vers {} ({}/{})'.format(
            self._status(reply), final_host, self._redirect_count, MAX_REDIRECTS))
        # Rend d'abord obsoletes les callbacks de l'ancienne reponse, puis
        # relance la connexion sans fermer la socket locale utilisee par VLC.
        self.reply = None
        reply.abort()
        reply.deleteLater()
        self._issue_request(destination, generation)

    def _metadata(self, reply, generation):
        if not self._valid(reply, generation) or self._header_sent:
            return
        status = self._status(reply)
        if status is None:
            return
        if status in REDIRECT_CODES:
            self._follow_redirect(reply, generation)
            return
        if status < 200 or status >= 300:
            host = urlsplit(reply.url().toString()).hostname or '?'
            self._failure('Serveur {} : HTTP {} (apres {} redirection(s)).'.format(
                host, status, self._redirect_count))
            return
        mime = bytes(reply.rawHeader(b'Content-Type')).decode('ascii', 'replace') or 'audio/mpeg'
        if mime.lower().startswith('text/html'):
            self._failure('Le serveur renvoie une page HTML, pas un flux audio.')
            return
        # Ne jamais forwarder les en-tetes du serveur; seulement le type audio.
        headers = ('HTTP/1.1 200 OK\r\nContent-Type: {}\r\n'
                   'Cache-Control: no-store\r\nConnection: close\r\n\r\n').format(mime)
        self.socket.write(headers.encode('ascii', 'replace'))
        self._header_sent = True
        self.progress.emit('Flux audio recu via QGIS : HTTP {} · {}'.format(status, mime))

    def _available(self, reply, generation):
        if not self._valid(reply, generation):
            return
        if not self._header_sent:
            self._metadata(reply, generation)
        if not self._valid(reply, generation) or not self._header_sent:
            return
        data = bytes(reply.readAll())
        if data:
            self._has_data = True
            if self.socket.bytesToWrite() > 4 * 1024 * 1024:
                self._failure('Tampon audio sature : VLC ne consomme pas les donnees.')
                return
            self.socket.write(data)

    def _finished(self, reply, generation):
        if not self._valid(reply, generation):
            return
        if not self._header_sent:
            self._metadata(reply, generation)
        if not self._valid(reply, generation):
            return
        if reply.error() != QNetworkReply.NoError:
            self._failure('Reseau QGIS : {}'.format(reply.errorString()))
            return
        self._available(reply, generation)
        if not self._valid(reply, generation):
            return
        if not self._has_data:
            self._failure('Aucune donnee audio recue par QGIS.')
        elif self.socket:
            self.socket.disconnectFromHost()

    def _timeout(self, reply, generation):
        if self._valid(reply, generation) and not self._has_data:
            self._failure('Aucune donnee audio apres 16 s (proxy, serveur ou redirection ?).')

    def _failure(self, message):
        self._cancel_active()
        self.failed.emit(message)

    def _disconnected(self, sock, generation):
        if generation != self._generation or sock is not self.socket:
            sock.deleteLater()
            return
        self._cancel_active()

    def _cancel_active(self):
        self._generation += 1
        reply, sock = self.reply, self.socket
        self.reply = None
        self.socket = None
        self._header_sent = False
        self._has_data = False
        self._visited = set()
        self._redirect_count = 0
        self._request_buffer = bytearray()
        if reply:
            reply.abort()
            reply.deleteLater()
        if sock:
            sock.disconnectFromHost()
            sock.deleteLater()

    def shutdown(self):
        self._cancel_active()
        self.server.close()
