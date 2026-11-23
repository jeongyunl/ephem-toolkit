"""Final OEM metadata application for progressive play-oem loading."""

from __future__ import annotations

from .. import playback_data
from ..display_time import format_tt
from .player_app_state import PlayerAppState


class PlayerIncrementalMetadataMixin:
    """Apply validated completion metadata and refresh player metadata views."""

    def _finish_incremental_metadata(self: PlayerAppState, completion) -> None:
        if completion is None:
            return
        meta = dict(completion.meta)
        center_name = str(meta.get("CENTER_NAME", ""))
        frame_name = str(meta.get("REF_FRAME", ""))
        self._oem_interpolation = str(meta.get("INTERPOLATION", "")) or None
        interpolation_degree = meta.get("INTERPOLATION_DEGREE")
        self._oem_interpolation_degree = (
            None if interpolation_degree is None else int(interpolation_degree)
        )
        self._metadata_details = (
            ("Object ID", str(meta.get("OBJECT_ID", ""))),
            ("Time system", str(meta.get("TIME_SYSTEM", ""))),
            ("Frame epoch", str(meta.get("REF_FRAME_EPOCH", ""))),
            ("Usable start", str(meta.get("USEABLE_START_TIME", ""))),
            ("Usable stop", str(meta.get("USEABLE_STOP_TIME", ""))),
            ("Interpolation", self._oem_interpolation or ""),
            (
                "Interpolation degree",
                ""
                if self._oem_interpolation_degree is None
                else str(self._oem_interpolation_degree),
            ),
        )
        self.object_id = dict(self._metadata_details).get("Object ID", "").strip()
        metadata_bounds = playback_data.oem_slider_bounds(
            str(meta.get("START_TIME", "")),
            str(meta.get("STOP_TIME", "")),
            (self.clock.t_start, self.clock.t_end),
            time_system=str(meta.get("TIME_SYSTEM", "UTC")) or "UTC",
        )
        self._slider_bounds = (
            min(self._slider_bounds[0], metadata_bounds[0]),
            max(self._slider_bounds[1], metadata_bounds[1]),
        )
        final_object_name = str(meta.get("OBJECT_NAME", "")).strip()
        if final_object_name:
            self.object_name = final_object_name
        self.status_bar.set_object(self.object_name, self.object_id)
        self.frame_context = (
            " / ".join(
                value for value in (frame_name.strip(), center_name.strip()) if value
            )
            or "Frame metadata unavailable"
        )
        self._dashboard_context.update(
            {
                "object": self.object_name,
                "frame": frame_name,
                "center": center_name,
                "time_span": (
                    f"{format_tt(self.clock.t_start, self._display_time_zone)} - "
                    f"{format_tt(self.clock.t_end, self._display_time_zone)}"
                ),
                "sample_count": str(completion.state_count),
            }
        )
        if self._use_oem_interpolation:
            self.cursor.set_interpolation(
                self._oem_interpolation,
                self._oem_interpolation_degree,
            )
        if (
            self._store_state.active is not None
            and self._store_state.view_context is not None
        ):
            self._store_state.view_context = self._store_state.view_context.refresh()
        self.control_window.update_active_interpolation(
            self._active_interpolation_summary()
        )
        if self._store_state.view_context is not None:
            self._store_state.view_context = self._store_state.view_context.refresh()
            self._publish_range_hint()
            self._queue_store_view_refresh()
        self._refresh_state.incremental_view_refresh_pending = True
