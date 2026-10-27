"""Selection state shared by Ground Station views in one graph stack."""

from __future__ import annotations

from collections.abc import Callable, Collection
from dataclasses import dataclass

IntervalKey = tuple[float, float]


@dataclass(frozen=True)
class StationAnalysisSelection:
    """Station and stable interval identity selected in one graph stack."""

    station_id: str | None = None
    interval_key: IntervalKey | None = None


class StationAnalysisContext:
    """Publish selection changes between peer Ground Station panels."""

    def __init__(self) -> None:
        self._selection = StationAnalysisSelection()
        self._listeners: dict[int, Callable[[StationAnalysisSelection], None]] = {}
        self._next_listener_id = 0

    @property
    def selection(self) -> StationAnalysisSelection:
        return self._selection

    def select_station(self, station_id: str | None) -> None:
        if station_id != self._selection.station_id:
            self._publish(StationAnalysisSelection(station_id))

    def select_interval(self, interval_key: IntervalKey | None) -> None:
        selection = StationAnalysisSelection(
            self._selection.station_id, interval_key
        )
        self._publish(selection)

    def retain_stations(self, station_ids: Collection[str]) -> None:
        """Retain a valid station selection and clear stale interval identity."""
        selected_id = self._selection.station_id
        if selected_id is not None and selected_id not in station_ids:
            self._publish(StationAnalysisSelection())
        else:
            self.select_interval(None)

    def subscribe(
        self, callback: Callable[[StationAnalysisSelection], None]
    ) -> Callable[[], None]:
        listener_id = self._next_listener_id
        self._next_listener_id += 1
        self._listeners[listener_id] = callback

        def unsubscribe() -> None:
            self._listeners.pop(listener_id, None)

        return unsubscribe

    def _publish(self, selection: StationAnalysisSelection) -> None:
        if selection == self._selection:
            return
        self._selection = selection
        for callback in tuple(self._listeners.values()):
            callback(selection)
