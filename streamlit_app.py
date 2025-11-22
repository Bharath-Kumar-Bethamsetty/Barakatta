import random
import time
import streamlit as st
import streamlit.components.v1 as components

# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------
st.set_page_config(
    page_title="Ashta Chamma / Barakatta",
    page_icon="🎲",
    layout="wide",
)

# ---------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------
PLAYER_EMOJIS = ["🔴", "🔵", "🟢", "🟡"]
PLAYER_COLORS = ["#e03131", "#1971c2", "#2b8a3e", "#f59f00"]  # red, blue, green, yellow
ROLL_VALUES = [1, 2, 3, 4, 8]  # cowrie-style
TOKENS_PER_PLAYER = 4
BOARD_SIZE = 7  # 7x7 board

# 13 safe cells for this 7x7 Ashta Chamma board (0-indexed)
SAFE_X_COORDS = {
    (0, 0), (0, 3), (0, 6),
    (1, 1), (1, 5),
    (3, 0), (3, 3), (3, 6),
    (5, 1), (5, 5),
    (6, 0), (6, 3), (6, 6),
}

# ---------------------------------------------------------
# GLOBAL STYLES
# ---------------------------------------------------------
def inject_global_styles():
    st.markdown(
        """<style>
html, body, [data-testid="stAppViewContainer"] {
    background: radial-gradient(circle at top left, #f1e3c7, #d0b894 40%, #a47c48 100%);
}

.main-card {
    background: rgba(255, 255, 255, 0.92);
    border-radius: 18px;
    padding: 1.5rem 1.8rem;
    box-shadow: 0 18px 40px rgba(0, 0, 0, 0.25);
    backdrop-filter: blur(4px);
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #3a2a18, #534030);
    color: #f6f1e4;
}
section[data-testid="stSidebar"] * {
    color: #f6f1e4 !important;
}

button[kind="primary"] {
    border-radius: 999px !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    padding: 0.6rem 1rem !important;
}

.dice {
    display: inline-block;
    font-size: 3rem;
    animation: dice-spin 0.6s ease-out;
}
@keyframes dice-spin {
    0% { transform: rotate(0deg) scale(0.8); }
    40% { transform: rotate(180deg) scale(1.1); }
    100% { transform: rotate(360deg) scale(1.0); }
}

@media (max-width: 768px) {
    .main-card {
        padding: 1rem 0.8rem;
        border-radius: 0;
        box-shadow: none;
    }
}
</style>""",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------
# SOUNDS
# ---------------------------------------------------------
SOUND_URLS = {
    "step": "https://actions.google.com/sounds/v1/cartoon/wood_plank_flicks.ogg",
    "capture": "https://actions.google.com/sounds/v1/cartoon/clang_and_wobble.ogg",
    "win": "https://actions.google.com/sounds/v1/cartoon/concussive_hit_guitar_boing.ogg",
    "roll": "https://actions.google.com/sounds/v1/cartoon/boing.ogg",
}


def trigger_sound(kind: str):
    if "sound_to_play" not in st.session_state:
        st.session_state.sound_to_play = None
    st.session_state.sound_to_play = kind


def render_sound_player():
    kind = st.session_state.get("sound_to_play")
    if not kind:
        return
    url = SOUND_URLS.get(kind)
    if url:
        components.html(
            f"""
<html><body>
<audio autoplay style="display:none;">
    <source src="{url}" type="audio/ogg">
</audio>
</body></html>
""",
            height=0,
        )
    st.session_state.sound_to_play = None


# ---------------------------------------------------------
# BOARD PATHS
# ---------------------------------------------------------
def build_paths(board_size=BOARD_SIZE):
    """
    7x7 board with 3 layers, per-player paths:

    For each player:
    - Full outer ring (7x7 perimeter), starting at side midpoint
    - Full middle ring (5x5 perimeter)
    - Full inner ring (3x3 perimeter)
    - Center cell (home 🏡)

    This guarantees:
    - You ALWAYS complete a whole layer before entering the next.
    - All safe cells on each ring are actually visited.
    """

    N = board_size
    assert N % 2 == 1, "Board size must be odd (7x7 for Ashta Chamma)"

    def ring(layer: int):
        """
        Build a perimeter ring at 'layer':
        layer = 0 -> outer 7x7
        layer = 1 -> middle 5x5
        layer = 2 -> inner 3x3
        """
        min_r = layer
        max_r = N - 1 - layer
        min_c = layer
        max_c = N - 1 - layer

        coords = []
        # top row
        for c in range(min_c, max_c + 1):
            coords.append((min_r, c))
        # right col
        for r in range(min_r + 1, max_r + 1):
            coords.append((r, max_c))
        # bottom row
        for c in range(max_c - 1, min_c - 1, -1):
            coords.append((max_r, c))
        # left col
        for r in range(max_r - 1, min_r, -1):
            coords.append((r, min_c))
        return coords

    outer = ring(0)   # 7x7 perimeter
    middle = ring(1)  # 5x5 perimeter
    inner = ring(2)   # 3x3 perimeter

    center = (N // 2, N // 2)  # (3,3) for 7x7

    # Starting cells on the outer ring (midpoints of each side)
    outer_starts = [
        (0, N // 2),      # Player 1 - top middle (0,3)
        (N // 2, N - 1),  # Player 2 - right middle (3,6)
        (N - 1, N // 2),  # Player 3 - bottom middle (6,3)
        (N // 2, 0),      # Player 4 - left middle (3,0)
    ]

    # Entry points for middle ring (2nd layer)
    middle_starts = [
        (1, N // 2),      # Player 1: (1,3)
        (N // 2, N - 2),  # Player 2: (3,5)
        (N - 2, N // 2),  # Player 3: (5,3)
        (N // 2, 1),      # Player 4: (3,1)
    ]

    # Entry points for inner ring (3rd layer)
    inner_starts = [
        (2, N // 2),      # Player 1: (2,3)
        (N // 2, N - 3),  # Player 2: (3,4)
        (N - 3, N // 2),  # Player 3: (4,3)
        (N // 2, 2),      # Player 4: (3,2)
    ]

    paths = []

    for p in range(4):
        # ----- outer ring path for this player -----
        o_start = outer_starts[p]
        o_idx = outer.index(o_start)
        outer_path = [outer[(o_idx + i) % len(outer)] for i in range(len(outer))]

        # ----- middle ring path -----
        m_start = middle_starts[p]
        m_idx = middle.index(m_start)
        middle_path = [middle[(m_idx + i) % len(middle)] for i in range(len(middle))]

        # ----- inner ring path -----
        i_start = inner_starts[p]
        i_idx = inner.index(i_start)
        inner_path = [inner[(i_idx + i) % len(inner)] for i in range(len(inner))]

        # Full path for this player: outer → middle → inner → center
        path = outer_path + middle_path + inner_path + [center]
        paths.append(path)

    # NOTE: we now also return middle_starts and inner_starts
    return paths, outer_starts, center, middle_starts, inner_starts


# ---------------------------------------------------------
# GAME STATE
# ---------------------------------------------------------
def init_session():
    if "initialized" not in st.session_state:
        st.session_state.initialized = True
        st.session_state.game_started = False
        st.session_state.num_players = 2
        st.session_state.player_names = [f"Player {i+1}" for i in range(4)]
        st.session_state.sound_to_play = None
        st.session_state.animation_info = None


def reset_game(num_players, player_names):
    paths, start_coords, center, middle_starts, inner_starts = build_paths(BOARD_SIZE)

    st.session_state.num_players = num_players
    st.session_state.player_names = player_names
    st.session_state.paths = paths
    st.session_state.start_coords = start_coords
    st.session_state.middle_starts = middle_starts
    st.session_state.inner_starts = inner_starts
    st.session_state.center = center
    st.session_state.board_size = BOARD_SIZE

    # safe for captures: 13 safe cells + the 4 start cells
    st.session_state.safe_cells = set(SAFE_X_COORDS).union(start_coords)

    path_len = len(paths[0])
    st.session_state.positions = [
        [0 for _ in range(TOKENS_PER_PLAYER)]
        for _ in range(num_players)
    ]

    st.session_state.current_player = 0
    st.session_state.roll_value = None
    st.session_state.winner = None
    st.session_state.last_message = "Game started! 🔴 Player 1 begins."
    st.session_state.game_started = True
    st.session_state.sound_to_play = None
    st.session_state.animation_info = None



# ---------------------------------------------------------
# GAME LOGIC
# ---------------------------------------------------------
def roll_shells():
    value = random.choice(ROLL_VALUES)
    st.session_state.roll_value = value
    p = st.session_state.current_player
    name = st.session_state.player_names[p]
    st.session_state.last_message = f"{PLAYER_EMOJIS[p]} **{name}** rolled **{value}**."
    trigger_sound("roll")


def get_valid_moves(player, roll):
    positions = st.session_state.positions[player]
    path_len = len(st.session_state.paths[player])
    valid = []
    for idx, pos in enumerate(positions):
        if pos == path_len:
            continue
        new_pos = pos + roll
        if new_pos <= path_len:
            valid.append(idx)
    return valid


def finalize_move_effects(player, token_index, roll, new_pos):
    """Run after animation: capture / win / next turn."""
    positions = st.session_state.positions
    paths = st.session_state.paths
    path = paths[player]
    path_len = len(path)

    coord = None
    if new_pos > 0:
        coord = path[new_pos - 1]

    captured_any = False
    if coord is not None and coord not in st.session_state.safe_cells:
        for op in range(st.session_state.num_players):
            if op == player:
                continue
            op_path = paths[op]
            for ti, op_steps in enumerate(positions[op]):
                if op_steps == 0 or op_steps == len(op_path):
                    continue
                op_coord = op_path[op_steps - 1]
                if op_coord == coord:
                    positions[op][ti] = 0
                    captured_any = True
                    st.session_state.last_message = (
                        f"{PLAYER_EMOJIS[player]} **{st.session_state.player_names[player]}** "
                        f"captured {PLAYER_EMOJIS[op]} **{st.session_state.player_names[op]}**'s token!"
                    )
    if captured_any:
        trigger_sound("capture")

    if all(pos == path_len for pos in positions[player]):
        st.session_state.winner = player
        st.session_state.last_message = (
            f"🏆 {PLAYER_EMOJIS[player]} **{st.session_state.player_names[player]}** wins the game!"
        )
        st.session_state.roll_value = None
        trigger_sound("win")
        return

    if roll in (4, 8) and st.session_state.winner is None:
        st.session_state.last_message += " 🎁 Extra turn for rolling **4** or **8**!"
    else:
        st.session_state.current_player = (
            (player + 1) % st.session_state.num_players
        )

    st.session_state.roll_value = None


def schedule_animation(player, token_index, roll):
    positions = st.session_state.positions
    path_len = len(st.session_state.paths[player])
    old_pos = positions[player][token_index]
    new_pos = old_pos + roll
    if new_pos > path_len:
        return
    st.session_state.animation_info = {
        "player": player,
        "token_index": token_index,
        "from_pos": old_pos,
        "to_pos": new_pos,
        "roll": roll,
    }


def run_animation(board_placeholder):
    anim = st.session_state.get("animation_info")
    if not anim:
        with board_placeholder:
            render_board()
        return

    p = anim["player"]
    t = anim["token_index"]
    from_pos = anim["from_pos"]
    to_pos = anim["to_pos"]
    roll = anim["roll"]

    positions = st.session_state.positions

    for step_pos in range(from_pos + 1, to_pos + 1):
        positions[p][t] = step_pos
        with board_placeholder:
            render_board()
        trigger_sound("step")
        time.sleep(0.5)

    finalize_move_effects(p, t, roll, to_pos)
    st.session_state.animation_info = None


# ---------------------------------------------------------
# BOARD RENDERING (HTML via components.html)
# ---------------------------------------------------------
def build_cell_token_map():
    cell_tokens = {}
    positions = st.session_state.positions
    paths = st.session_state.paths
    for p in range(st.session_state.num_players):
        path = paths[p]
        for t_idx, steps in enumerate(positions[p]):
            if steps <= 0 or steps > len(path):
                continue
            coord = path[steps - 1]
            cell_tokens.setdefault(coord, []).append((p, t_idx))
    return cell_tokens


def render_board():
    N = st.session_state.board_size
    center = st.session_state.center
    paths = st.session_state.paths
    start_coords = st.session_state.start_coords
    middle_starts = st.session_state.get("middle_starts", [])
    inner_starts = st.session_state.get("inner_starts", [])
    num_players = st.session_state.num_players

    # For coloring: each player owns THREE axial cells:
    # - start on outer ring
    # - entry to 2nd layer
    # - entry to 3rd layer
    highlight_owner = {}
    for p in range(num_players):
        for arr in (start_coords, middle_starts, inner_starts):
            if arr and p < len(arr):
                coord = arr[p]
                highlight_owner[coord] = p

    cell_tokens = build_cell_token_map()

    table_html = "<div style='display:inline-block;border:4px solid #222;padding:4px;background:#f1e3c7;'><table style='border-collapse:collapse;'>"

    for r in range(N):
        table_html += "<tr>"
        for c in range(N):
            coord = (r, c)
            tokens_here = cell_tokens.get(coord, [])
            is_center = coord == center
            is_safe = coord in SAFE_X_COORDS
            owner_player = highlight_owner.get(coord)

            # how many tokens in this cell?
            num_tokens = len(tokens_here)

            # ----- dynamic token size based on count -----
            if num_tokens <= 1:
                token_size = 26
            elif num_tokens == 2:
                token_size = 22
            elif num_tokens == 3:
                token_size = 20
            else:
                token_size = 18  # 4+ tokens, make them smaller

            circle_size = token_size
            font_size = max(token_size - 8, 10)

            # build token HTML
            if tokens_here:
                token_htmls = []
                for (p, t) in tokens_here:
                    color = PLAYER_COLORS[p]
                    token_htmls.append(
                        f"<span style='display:inline-flex;align-items:center;justify-content:center;"
                        f"width:{circle_size}px;height:{circle_size}px;border-radius:50%;"
                        f"background:{color};color:#ffffff;font-size:{font_size}px;font-weight:600;"
                        f"margin:1px 2px;'>{t+1}</span>"
                    )
                token_str = "".join(token_htmls)
            else:
                token_str = "&nbsp;"

            # ----- marker (🏡 or gold ❌) -----
            if is_center:
                house_size = 20 if num_tokens <= 2 else 16
                marker_html = f"<span style='font-size:{house_size}px;'>🏡</span>"
            elif is_safe:
                safe_size = 18 if num_tokens <= 2 else 14
                marker_html = f"<span style='color:#d4af37;font-size:{safe_size}px;'>❌</span>"
            else:
                marker_html = "&nbsp;"

            # ----- borders -----
            outer_border = (r in (0, N - 1) or c in (0, N - 1))
            border_width = "2px" if outer_border else "1px"
            border_color = "#222"

            # ----- background priority: center > entry cells > safe cell > normal -----
            if is_center:
                bg = "#ffefc2"  # home cell
            elif owner_player is not None:
                # start + entry cells tinted by player color
                bg = PLAYER_COLORS[owner_player] + "44"
            elif is_safe:
                bg = "#fff3cc"  # general safe cells
            else:
                bg = "#f6f1e4"

            table_html += (
                f"<td style='border:{border_width} solid {border_color};padding:2px;'>"
                f"<div style='width:48px;height:48px;display:flex;flex-direction:column;"
                f"align-items:center;justify-content:center;background:{bg};'>"
                f"<div style=\"font-size:13px;line-height:1;opacity:0.9;\">{marker_html}</div>"
                f"<div style='display:flex;flex-wrap:wrap;justify-content:center;"
                f"align-items:center;gap:2px;margin-top:2px;'>"
                f"{token_str}"
                f"</div></div></td>"
            )
        table_html += "</tr>"

    table_html += "</table></div>"

    components.html(
        f"<html><body>{table_html}</body></html>",
        height=BOARD_SIZE * 60 + 40,
    )

# ---------------------------------------------------------
# SIDEBAR & STATUS
# ---------------------------------------------------------
def sidebar_setup():
    with st.sidebar:
        st.markdown("## ⚙️ Game Setup")

        num_players = st.slider(
            "Number of players",
            min_value=2,
            max_value=4,
            value=st.session_state.get("num_players", 2),
        )

        existing_names = st.session_state.get(
            "player_names",
            [f"Player {i+1}" for i in range(4)],
        )

        player_names = []
        for i in range(num_players):
            name = st.text_input(
                f"Name for Player {i+1}",
                value=existing_names[i] if i < len(existing_names) else f"Player {i+1}",
                key=f"name_{i}",
            )
            player_names.append(name.strip() or f"Player {i+1}")

        if st.button("🔁 Start / Reset Game", use_container_width=True):
            reset_game(num_players, player_names)
            st.rerun()

        st.markdown("---")
        st.markdown("### 🎭 Player legend")
        for i in range(num_players):
            st.markdown(f"- {PLAYER_EMOJIS[i]} **{player_names[i]}**")

        st.markdown("---")
        st.markdown(
            """
            ### 📜 Rules (simplified)
            - Each player has **4 tokens**.
            - Roll gives one of **1, 2, 3, 4, 8**.
            - Tokens move around the **outer loop**, then inwards to the **center (🏡)**.
            - **13 gold-❌ cells** are special safe spots.
            - Start cells are also safe.
            - Land on an opponent on a non-safe cell → **capture**.
            - Roll **4** or **8** → **extra turn**.
            - First player with **all 4 tokens in the center** wins.
            """
        )

def render_status_and_actions():
    st.markdown("---")

    left, right = st.columns([2.5, 1.5])

    with left:
        if not st.session_state.game_started:
            st.info("Set players and click **Start / Reset Game** to begin.")
            return

        winner = st.session_state.winner

        if winner is None:
            p = st.session_state.current_player
            name = st.session_state.player_names[p]
            st.subheader(f"Current turn: {PLAYER_EMOJIS[p]} {name}")
        else:
            st.subheader("Game over")

        st.markdown(st.session_state.last_message or "")

        path_len = len(st.session_state.paths[0])
        st.markdown("#### Token progress")
        for p in range(st.session_state.num_players):
            finished = sum(
                1 for pos in st.session_state.positions[p] if pos == path_len
            )
            st.markdown(
                f"{PLAYER_EMOJIS[p]} **{st.session_state.player_names[p]}** – "
                f"{finished}/{TOKENS_PER_PLAYER} tokens finished"
            )

    with right:
        if not st.session_state.game_started:
            return

        winner = st.session_state.winner
        roll_value = st.session_state.roll_value
        current_player = st.session_state.current_player

        st.markdown("### 🎮 Actions")

        if winner is not None:
            st.success(
                f"🏆 {PLAYER_EMOJIS[winner]} {st.session_state.player_names[winner]} is the winner!"
            )
            st.balloons()
            st.info("Use **Start / Reset Game** in the sidebar to play again.")
            return

        anim_running = st.session_state.get("animation_info") is not None

        roll_disabled = (roll_value is not None) or anim_running
        if st.button(
            "🎲 Roll shells",
            use_container_width=True,
            disabled=roll_disabled,
        ):
            roll_shells()
            st.rerun()

        if roll_value is not None:
            st.markdown(
                "<div style='text-align:center; margin-top:0.5rem;'>"
                "<span class='dice'>🎲</span>"
                "<div style='font-size:1.1rem; margin-top:0.3rem;'>You rolled: "
                f"<b>{roll_value}</b></div></div>",
                unsafe_allow_html=True,
            )

            valid_tokens = get_valid_moves(current_player, roll_value)
            if not valid_tokens:
                st.warning("No valid moves for this roll. Turn passes to next player.")
                st.session_state.roll_value = None
                st.session_state.current_player = (
                    (current_player + 1) % st.session_state.num_players
                )
                st.session_state.last_message = "No moves possible, so the turn was skipped."
                st.rerun()
            else:
                st.markdown("Choose a token to move:")
                for t in valid_tokens:
                    label = f"Move token {t+1}"
                    if st.button(
                        label,
                        key=f"move_{current_player}_{t}",
                        use_container_width=True,
                        disabled=anim_running,
                    ):
                        schedule_animation(current_player, t, roll_value)
                        st.rerun()


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
def main():
    inject_global_styles()
    init_session()
    sidebar_setup()

    st.markdown('<div class="main-card">', unsafe_allow_html=True)
    st.title("🎲 Ashta Chamma / Barakatta")
    st.caption("Local hot-seat version – play together on one screen.")

    if st.session_state.game_started:
        st.markdown("### Game Board")
        board_placeholder = st.empty()
        if st.session_state.animation_info:
            run_animation(board_placeholder)
        else:
            with board_placeholder:
                render_board()
    else:
        st.info("Configure the game in the **left sidebar** and press **Start / Reset Game**.")

    render_status_and_actions()
    st.markdown("</div>", unsafe_allow_html=True)

    render_sound_player()


if __name__ == "__main__":
    main()
