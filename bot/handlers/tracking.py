"""Seguimiento semanal: aceptar/rechazar la oferta, la decisión del admin, /seguimientos y dejar de seguir."""

import re

from telegram import InlineKeyboardMarkup

from ..core.models import TrackStatus
from ..core.text import e, plain
from ..tracking import Tracker
from ..tracking.schedule import Schedule
from ..ui.keyboards import button
from .base import HTML, Access, ButtonCommand, ChatCommand, register


class TrackButton(ButtonCommand):
    """Botón con el id del seguimiento; solo vale para su dueño (o para el admin, si owner_only=False)."""
    owner_only = True
    auto_answer = False

    async def execute(self, ctx):
        t = self.k.db.track_get(int(ctx.parts[0]))
        if t is None:
            return await ctx.alert(ctx.say("track_gone"))
        if t.chat_id != ctx.chat_id and (self.owner_only or not ctx.is_admin):
            return await ctx.alert(ctx.say("not_authorized"))
        await ctx.query.answer()
        await self.run(ctx, t)

    async def run(self, ctx, t): ...


@register
class TrackYes(TrackButton):
    pattern = rf"^{Tracker.YES}:\d+$"

    async def run(self, ctx, t):
        await ctx.query.edit_message_reply_markup(None)
        text = await self.k.tracker.accept(t)
        await ctx.query.edit_message_text(text, parse_mode=HTML)


@register
class TrackNo(TrackButton):
    pattern = rf"^{Tracker.NO}:\d+$"

    async def run(self, ctx, t):
        await ctx.query.edit_message_text(await self.k.tracker.decline(t), parse_mode=HTML)


@register
class TrackDecision(ButtonCommand):
    pattern = rf"^({Tracker.APPROVE}|{Tracker.REJECT}):\d+$"
    access = Access.ADMIN
    denied_key = "not_admin"
    auto_answer = False

    async def execute(self, ctx):
        tr = self.k.tracker
        t = self.k.db.track_get(int(ctx.parts[0]))
        if t is None:
            return await ctx.alert(ctx.say("track_gone"))
        if t.status not in TrackStatus.OPEN:
            return await ctx.alert(ctx.say("already_decided", status=t.status))
        head = tr.admin_text(t)
        if ctx.query.data.startswith(Tracker.REJECT):
            await ctx.query.answer("Rechazado")
            return await ctx.query.edit_message_text(head + "\n\n" + await tr.reject(t), parse_mode=HTML,
                                                     disable_web_page_preview=True)
        await ctx.query.answer("Marchando…")
        ok, text = await tr.approve(t)
        t = self.k.db.track_get(t.id)
        await ctx.query.edit_message_text(tr.admin_text(t) + "\n\n" + text, parse_mode=HTML,
                                          disable_web_page_preview=True,
                                          reply_markup=None if ok else tr.admin_keyboard(t, retry=True))


@register
class TrackStop(TrackButton):
    pattern = rf"^{Tracker.STOP}:\d+$"
    owner_only = False

    async def run(self, ctx, t):
        mine = t.chat_id == ctx.chat_id
        stopped = await self.k.tracker.stop(t, None if mine else "track_stopped_by_boss")
        key = "track_stopped" if stopped else "track_gone"
        text, kb = Seguimientos.render(self.k, ctx.chat_id)
        await ctx.query.edit_message_text(ctx.say(key, title=t.title) + "\n\n" + text, parse_mode=HTML,
                                          reply_markup=kb)


def short_name(user_name: str) -> str:
    """«luis sagarvinaga (@Luisito_kun)» -> «@Luisito_kun» (o el nombre, si no tiene usuario)."""
    m = re.search(r"\((@[^)]+)\)", user_name or "")
    return m.group(1) if m else (user_name or "?").strip()


@register
class Seguimientos(ChatCommand):
    names = ("seguimientos", "vigilar")

    @staticmethod
    def render(kuro, chat_id: int) -> tuple[str, InlineKeyboardMarkup | None]:
        say = kuro.persona.to(chat_id)
        admin = kuro.is_admin(chat_id)
        if not kuro.tracker.enabled:
            return say("track_disabled"), None
        states = (TrackStatus.ACTIVE, TrackStatus.PENDING, TrackStatus.PROCESSING, TrackStatus.FAILED)
        items = kuro.db.track_list(None if admin else chat_id, states)
        if not items:
            return say("track_none"), None
        lines, rows = [say("track_list_head", count=len(items))], []
        for t in items:
            state = "" if t.status == TrackStatus.ACTIVE else " — ⏳ pendiente del miauestro" if (
                t.status == TrackStatus.PENDING) else " — ⚠️ falló al crearse"
            shared = " — 🤝 compartida, no gasta cupo" if t.shared and not admin else ""
            if admin:
                # al admin le salen las de todos: cada línea y cada botón dicen de quién es
                owner = "tú" if kuro.is_admin(t.chat_id) else short_name(t.user_name)
                lines.append(f"📡 <b>{e(t.title)}</b> · 👤 {e(owner)}\n"
                             f"    {e(Schedule.from_dict(t.schedule).describe())}{state}")
                rows.append([button(f"🗑 {owner} · {plain(t.title)}", f"{Tracker.STOP}:{t.id}", 48)])
                continue
            lines.append(f"📡 <b>{e(t.title)}</b>\n    {e(Schedule.from_dict(t.schedule).describe())}{state}{shared}")
            rows.append([button(f"🗑 {plain(t.title)}", f"{Tracker.STOP}:{t.id}", 40)])
        if not admin:
            lines.append(say("track_list_limit", count=kuro.db.track_counted(chat_id), limit=kuro.tracker.limit))
        return "\n".join(lines), InlineKeyboardMarkup(rows)

    async def execute(self, ctx):
        text, kb = self.render(self.k, ctx.chat_id)
        await ctx.reply(text, reply_markup=kb)
