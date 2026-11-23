"""File-specific timeline and time-scrubber state restoration."""

from __future__ import annotations

import warnings

from .. import clock, time_range
from ..display_time import format_tt
from ..saved_state import normalize_recent_path
from .player_app_state import PlayerAppState


class PlayerTimelineRestoreMixin:
    """Restore and apply saved playback, viewport, and plot-range state."""

    @staticmethod
    def _validate_saved_playback(
        playback_range: tuple[float, float] | None,
        coverage: tuple[float, float],
    ) -> tuple[float, float] | None:
        if playback_range is None:
            return None
        validated = time_range.validate_playback_range(playback_range, coverage)
        return validated.start_s, validated.end_s

    @staticmethod
    def _validate_saved_viewport(
        viewport: tuple[float, float] | None,
        coverage: tuple[float, float],
    ) -> tuple[float, float] | None:
        if viewport is None:
            return None
        if not coverage[0] <= viewport[0] < viewport[1] <= coverage[1]:
            return None
        return viewport

    def _prepare_scrubber_restore(
        self: PlayerAppState,
        path: str,
        coverage: tuple[float, float],
        *,
        use_defaults_for_invalid_state: bool,
    ) -> (
        tuple[
            tuple[float, float],
            tuple[float, float],
            float,
            tuple[float, float],
            time_range.PlotTimeRange,
        ]
        | None
    ):
        settings = (
            self._saved_state.file_settings.get(normalize_recent_path(path))
            if self._saved_state is not None
            else None
        )
        playback = (
            coverage[0],
            coverage[0]
            + min(
                clock.PlaybackClock.DEFAULT_PLAYBACK_SPAN_S,
                coverage[1] - coverage[0],
            ),
        )
        scrubber = settings.time_scrubber if settings is not None else None
        if settings is not None and settings.playback_range is not None:
            try:
                saved_playback = self._validate_saved_playback(
                    settings.playback_range, coverage
                )
            except ValueError:
                if not use_defaults_for_invalid_state:
                    return None
                scrubber = None
            else:
                if saved_playback is not None:
                    playback = saved_playback
        current_time = scrubber.current_time_tt if scrubber is not None else None
        viewport = scrubber.viewport_tt if scrubber is not None else None
        if current_time is not None and not playback[0] <= current_time <= playback[1]:
            if not use_defaults_for_invalid_state:
                return None
            scrubber = None
            current_time = None
            viewport = None
        if scrubber is not None and viewport is not None:
            viewport = self._validate_saved_viewport(viewport, coverage)
            if viewport is None and not use_defaults_for_invalid_state:
                return None
        if current_time is None:
            current_time = coverage[0]
        if viewport is None:
            viewport = coverage
        plot_rule = self.plot_time_range
        if settings is not None and settings.plot_range is not None:
            try:
                plot_rule = time_range.validate_plot_range(settings.plot_range)
            except ValueError:
                pass
            else:
                self.plot_time_range = plot_rule
        return coverage, playback, current_time, viewport, plot_rule

    def _restore_scrubber_from_metadata(
        self: PlayerAppState,
        path: str,
        coverage: tuple[float, float],
        *,
        use_defaults_for_invalid_state: bool = False,
    ) -> None:
        """Apply saved scrubber state as soon as its OEM domain is known."""
        if (
            self._timeline_restore_state.metadata_restored
            and self._timeline_restore_state.metadata_coverage == coverage
        ):
            return
        prepared = self._prepare_scrubber_restore(
            path,
            coverage,
            use_defaults_for_invalid_state=use_defaults_for_invalid_state,
        )
        if prepared is None:
            return
        _, playback, current_time, viewport, plot_rule = prepared

        self._timeline_restore_state.file_current_time_s = current_time
        self._load_state.cursor_anchor_s = current_time
        self._timeline_restore_state.viewport = viewport
        self._timeline_restore_state.playback_bounds = playback
        self._timeline_restore_state.file_playback_bounds = playback
        self._playback_handles_fixed_during_load = True
        self._playback_handle_bounds = playback
        self.workspace.set_time_range_controls(
            coverage,
            playback,
            plot_rule,
            current_time,
            viewport,
            playback,
            unloaded_from_s=self._load_state.loading_progress_s,
        )
        timeline_slider = getattr(self.workspace, "timeline_slider", None)
        set_viewport = getattr(timeline_slider, "set_viewport", None)
        if callable(set_viewport):
            set_viewport(viewport)
        span = viewport[1] - viewport[0]
        progress = 0.0 if span == 0.0 else (current_time - viewport[0]) / span
        self.workspace.update_timeline(
            progress,
            format_tt(current_time, self._display_time_zone),
            playing=False,
        )
        self._timeline_restore_state.metadata_restored = True
        self._timeline_restore_state.metadata_coverage = coverage
        self._timeline_restore_state.metadata_playback = playback
        self._timeline_restore_state.metadata_viewport = viewport
        self._timeline_restore_state.loading_locked = True
        self._apply_pending_playback_bounds()

    def _restore_file_timeline(
        self: PlayerAppState,
        path: str,
        target_clock: clock.PlaybackClock,
    ) -> tuple[float, float] | None:
        """Restore time bounds, playhead, and viewport once OEM coverage is known."""
        if self._saved_state is None:
            return None
        settings = self._saved_state.file_settings.get(path)
        if settings is None:
            return None

        if settings.playback_range is not None:
            try:
                bounds = time_range.validate_playback_range(
                    settings.playback_range,
                    (target_clock.t_start, target_clock.t_end),
                )
            except ValueError as error:
                settings.playback_range = None
                warnings.warn(
                    f"Ignoring saved playback range for {path}: {error}",
                    RuntimeWarning,
                    stacklevel=2,
                )
            else:
                target_clock.set_playback_bounds(bounds.start_s, bounds.end_s)

        if settings.time_scrubber is None:
            return None
        scrubber = settings.time_scrubber
        current_time = scrubber.current_time_tt
        if current_time is not None:
            if not (
                target_clock.playback_start <= current_time <= target_clock.playback_end
            ):
                scrubber.current_time_tt = None
                warnings.warn(
                    f"Ignoring saved time scrubber current time for {path}: "
                    "it is outside the playback range",
                    RuntimeWarning,
                    stacklevel=2,
                )
            else:
                target_clock.seek(current_time)
        viewport = scrubber.viewport_tt
        if viewport is not None and not (
            target_clock.t_start <= viewport[0] < viewport[1] <= target_clock.t_end
        ):
            scrubber.viewport_tt = None
            warnings.warn(
                f"Ignoring saved time scrubber viewport for {path}: "
                "it is outside OEM coverage",
                RuntimeWarning,
                stacklevel=2,
            )
            return None
        return viewport
