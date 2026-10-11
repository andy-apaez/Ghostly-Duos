// Twin Spirits — game server.
// Serves index.html and relays messages between two players in a room.
// The host's browser runs the game; this server only pairs players and forwards traffic.
const http = require('http');
const fs = require('fs');
const path = require('path');
const { WebSocketServer } = require('ws');

const PORT = process.env.PORT || 8080;
const INDEX = path.join(__dirname, 'index.html');
const CODE_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // no 0/O or 1/I

const server = http.createServer((req, res) => {
  const url = req.url.split('?')[0];
  if (url === '/' || url === '/index.html') {
    fs.readFile(INDEX, (err, data) => {
      if (err) { res.writeHead(500); return res.end('Failed to load game'); }
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-cache' });
      res.end(data);
    });
  } else if (url === '/config.js' || /^\/assets\/[\w.-]+\.(js|png)$/.test(url)) {
    fs.readFile(path.join(__dirname, url), (err, data) => {
      if (err) { res.writeHead(404); return res.end('Not found'); }
      res.writeHead(200, { 'Content-Type': url.endsWith('.js') ? 'text/javascript' : 'image/png', 'Cache-Control': 'no-cache' });
      res.end(data);
    });
  } else if (url === '/health') {
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end('ok');
  } else {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('Not found');
  }
});

const wss = new WebSocketServer({ server, maxPayload: 256 * 1024 });
const rooms = new Map(); // code -> { host, guest }

function newCode() {
  let code;
  do {
    code = Array.from({ length: 4 }, () => CODE_CHARS[Math.floor(Math.random() * CODE_CHARS.length)]).join('');
  } while (rooms.has(code));
  return code;
}

function sendJSON(ws, obj) {
  if (ws && ws.readyState === ws.OPEN) ws.send(JSON.stringify(obj));
}

function leaveRoom(ws) {
  const code = ws.room;
  if (!code) return;
  ws.room = null;
  const room = rooms.get(code);
  if (!room) return;
  rooms.delete(code);
  const other = room.host === ws ? room.guest : room.host;
  if (other) {
    other.room = null;
    sendJSON(other, { t: 'left' });
  }
}

wss.on('connection', ws => {
  ws.isAlive = true;
  ws.room = null;
  ws.on('pong', () => { ws.isAlive = true; });

  ws.on('message', raw => {
    const room = ws.room && rooms.get(ws.room);

    // Paired: forward everything to the other player without parsing.
    if (room && room.host && room.guest) {
      const other = room.host === ws ? room.guest : room.host;
      if (other.readyState === other.OPEN) other.send(raw.toString());
      return;
    }

    let msg;
    try { msg = JSON.parse(raw); } catch { return; }

    if (msg.t === 'host' && !ws.room) {
      const code = newCode();
      rooms.set(code, { host: ws, guest: null });
      ws.room = code;
      sendJSON(ws, { t: 'room', code });
      console.log(`room ${code} created (${rooms.size} open)`);
    } else if (msg.t === 'join' && !ws.room) {
      const code = String(msg.code || '').toUpperCase();
      const target = rooms.get(code);
      if (!target) return sendJSON(ws, { t: 'error', msg: 'No room with that code' });
      if (target.guest) return sendJSON(ws, { t: 'error', msg: 'That room is full' });
      target.guest = ws;
      ws.room = code;
      sendJSON(target.host, { t: 'start' });
      sendJSON(ws, { t: 'start' });
      console.log(`room ${code} started`);
    }
  });

  ws.on('close', () => leaveRoom(ws));
  ws.on('error', () => leaveRoom(ws));
});

// Drop connections that stop answering pings (closed laptops, lost Wi-Fi).
const heartbeat = setInterval(() => {
  for (const ws of wss.clients) {
    if (!ws.isAlive) { ws.terminate(); continue; }
    ws.isAlive = false;
    ws.ping();
  }
}, 15000);
wss.on('close', () => clearInterval(heartbeat));

server.listen(PORT, () => {
  console.log(`Twin Spirits running at http://localhost:${PORT}`);
});
