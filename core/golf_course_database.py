from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


class GolfCourseDatabase:
    def __init__(self, db_path: str = "data/golf/golf_courses.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        return sqlite3.connect(str(self.db_path))

    def _init_db(self) -> None:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                country TEXT,
                region TEXT,
                city TEXT,
                latitude REAL,
                longitude REAL,
                holes INTEGER,
                par_total INTEGER,
                source TEXT
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_courses_geo ON courses(latitude, longitude)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_courses_name ON courses(name)")
        conn.commit()
        conn.close()

    def upsert_course(self, course: Dict[str, Any]) -> None:
        conn = self._connect()
        cur = conn.cursor()

        name = course.get("name")
        country = course.get("country")
        city = course.get("city")

        cur.execute(
            "SELECT id FROM courses WHERE name = ? AND IFNULL(country,'') = IFNULL(?, '') AND IFNULL(city,'') = IFNULL(?, '')",
            (name, country, city),
        )
        row = cur.fetchone()

        values = (
            course.get("name"),
            course.get("country"),
            course.get("region"),
            course.get("city"),
            course.get("latitude"),
            course.get("longitude"),
            course.get("holes"),
            course.get("par_total"),
            course.get("source", "local"),
        )

        if row:
            cur.execute(
                """
                UPDATE courses
                SET name=?, country=?, region=?, city=?, latitude=?, longitude=?, holes=?, par_total=?, source=?
                WHERE id=?
                """,
                values + (row[0],),
            )
        else:
            cur.execute(
                """
                INSERT INTO courses (name, country, region, city, latitude, longitude, holes, par_total, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )

        conn.commit()
        conn.close()

    def import_json(self, json_path: str) -> Dict[str, Any]:
        path = Path(json_path)
        if not path.exists():
            return {"status": "error", "message": f"File not found: {json_path}"}

        data = json.loads(path.read_text(encoding="utf-8"))
        courses = data.get("courses", [])
        count = 0
        for course in courses:
            self.upsert_course(course)
            count += 1

        return {"status": "ok", "imported": count, "source": json_path}

    def search_by_name(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM courses
            WHERE name LIKE ?
            ORDER BY name ASC
            LIMIT ?
            """,
            (f"%{query}%", limit),
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def nearest_course(self, latitude: float, longitude: float, max_km: float = 20.0) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM courses WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

        best = None
        best_dist = None
        for row in rows:
            dist = self._haversine(latitude, longitude, float(row["latitude"]), float(row["longitude"]))
            if best is None or dist < best_dist:
                best = row
                best_dist = dist

        if best is not None and best_dist is not None and best_dist <= max_km:
            best["distance_km"] = round(best_dist, 3)
            return best
        return None

    def stats(self) -> Dict[str, Any]:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM courses")
        total = cur.fetchone()[0]
        cur.execute("SELECT country, COUNT(*) FROM courses GROUP BY country ORDER BY COUNT(*) DESC LIMIT 10")
        top_countries = [{"country": r[0], "count": r[1]} for r in cur.fetchall()]
        conn.close()
        return {
            "total_courses": total,
            "top_countries": top_countries,
            "db_path": str(self.db_path),
        }

    def _haversine(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371.0
        p1 = math.radians(lat1)
        p2 = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c