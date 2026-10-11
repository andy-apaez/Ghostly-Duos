# Twin Spirits

A two-player co-op pixel platformer. Play on one keyboard (Local Co-op) or over the internet (Host Online / Join Online).

## Run it

```sh
npm install
npm start
```

Open http://localhost:8080. To try online play on one computer, open that address in two browser tabs. In one tab choose **Host Online**; in the other choose **Join Online** and type the room code.

Opening `index.html` straight from disk still works for local co-op. Online play from a file uses the server at `ws://localhost:8080`, or the one given in `?server=wss://your-server`.

## The world

The Whispering Wood is one connected map, laid out like Hollow Knight. The camera frames each area, and shafts and tunnels link the areas.

- **Moonlit Edge** (start). Drop down the **Rootwell** into the hub.
- **Glowcap Hollow** (hub) has a lantern and a sealed door. Exits lead west, east and down.
- **Fern Thicket** (west) is a climb with a Spirit Mask at the top.
- **Thornwood** and **Thornwood Canopy** (east) hold a Moon Sigil.
- **Rootdeep** and **The Tangled Deep** (down) hold a Moon Sigil.
- Two sigils break the seal and open the way to the **Elder Grove**, where the Forest Wraith waits.

Two cracked walls hide secret rooms; hit them with your sword. Each **Spirit Mask** gives both ghosts +1 max health. Lanterns save progress and revive a fallen partner. Hold **Tab** (or the gamepad's Back button) to view the map. If one ghost is left off-screen for a moment, it gets pulled back to its partner.

The map is built in `buildLevel()` in `index.html` from `carve` (open space), `fill` (rock), `plat` (one-way ledges) and `thorns` calls. Camera framing comes from the `ZONES` list.

Debug views: `index.html#worldmap` renders the whole world as one image. `index.html#at-X-Y` starts a game at tile X,Y; add `-ff600` to fast-forward 600 frames (the boss room is at `#at-112-86`).

## Art and sprites

All character art comes from the sheets in `sprites/`. The game loads it from `assets/sprites.js`, which `tools/build_sprites.py` generates:

```sh
python3 tools/build_sprites.py     # needs Pillow, NumPy, SciPy and OpenCV
```

The script cuts every frame from the showcase sheets at native size (they're drawn at 3x and 4x), makes the cell backgrounds transparent, and packs everything into one atlas. It also turns `boss_room_v2_preview.gif` into the Elder Grove backdrop by removing the characters painted into it. Rerun the script after changing any sheet. If you add rows or reorder them, update the row lists at the top of the script.

- **Ghosts:** idle, run, jump, fall, dash, attack, hurt and death animations, plus a slash effect for each.
- **Mobs:** each has its own attack.
  - Arcane slime: goo waves.
  - Crystal golem: crystal shockwave.
  - Shroom mage: sky strike.
  - Hex lantern: hexflame breath.
  - Grimoire: rune beam.
  - Star moth: constellation trap.
- **Forest Wraith (boss):**
  - Wisp bolts, then a volley of thorn spears.
  - Root snares under each ghost.
  - A bramble ring with a warning circle first. After it the wraith is stunned and takes 1.5x damage.
  - From half health it also summons haunt fog.
- **Spirit Nova:** uses the `spirit_nova` effect.

## How online play works

- `server.js` serves the game and pairs two players by a 4-character room code. It forwards their messages and doesn't run any game logic.
- The **host** (white ghost) runs the whole game in their browser and sends a snapshot of the game to the guest 30 times a second.
- The **guest** (black ghost) sends their key presses 60 times a second and draws the snapshots, smoothing movement between them.
- Online, either key set (WASD or arrows) controls your ghost. Gamepads work too.

## Play with someone on your Wi-Fi

Run `npm start`, find your computer's local IP (macOS: `ipconfig getifaddr en0`), and have your partner open `http://<that-ip>:8080`.

## Deploy it (game on Vercel, relay on Render)

Vercel can host the game page but can't run the WebSocket relay, so the relay (`server.js`) goes on Render and the page points at it.

**1. Deploy the relay on Render**

1. Push this folder to a GitHub repo.
2. In Render, create a **New → Web Service** from the repo.
3. Build command: `npm install`. Start command: `npm start`. The free instance type is fine.
4. When it's live, copy its address, e.g. `https://twin-spirits.onrender.com`. Opening `/health` on it should show `ok`.

**2. Point the game at the relay**

In `config.js`, set the relay address with `wss://` in place of `https://`, then commit and push:

```js
window.GAME_CONFIG = {
  server: 'wss://twin-spirits.onrender.com'
};
```

**3. Deploy the game on Vercel**

1. In Vercel, **Add New → Project** and import the same repo.
2. Framework preset: **Other**. Leave the build command empty and the output directory as the project root.
3. Deploy, then share the `https://….vercel.app` link. That's the game link players use.

`.vercelignore` keeps the relay code and the source art out of the Vercel deployment; only `index.html`, `config.js` and `assets/` are published.

**How the game picks the relay:** a `?server=wss://…` in the link wins. Otherwise it uses `config.js`, except when the page is served from `localhost` or your local network, where it uses that same host so `npm start` keeps working. With `config.js` left empty, it uses whatever host served the page, so the Render URL also works on its own as a game link.

**Free-tier sleep:** Render's free relay sleeps after about 15 idle minutes and takes up to a minute to wake. The game starts waking it as soon as the page loads. If someone picks Host or Join while it's still waking, the lobby shows "waking the server" and keeps retrying for about 70 seconds. To avoid the wait, use a paid Render instance, which stays on.

Railway and Fly.io work the same way as Render; the relay reads its port from the `PORT` environment variable.

## Known limits

- The guest's ghost reacts after a delay equal to their ping, because the host runs the game. Under about 80 ms it's hard to notice.
- Rooms hold exactly two players. If either player leaves, the other gets a message and returns to the title screen.
# Ghostly-Duos
