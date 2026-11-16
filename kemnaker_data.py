import os
import json
import ssl
import urllib.request
import urllib.error
from datetime import datetime, date, timezone, timedelta

from paths import is_frozen, base_dir, resource_path

import re

UNITS = [
    {
        "slug": "menteri-ketenagakerjaan",
        "name": "Kementerian Ketenagakerjaan RI",
    },
    {
        "slug": "sekretariat-jendral",
        "name": "Sekretariat Jenderal",
    },
    {
        "slug": "inspektorat-jendral",
        "name": "Inspektorat Jenderal",
    },
    {
        "slug": "barenbang",
        "name": "Barenbang",
    },
    {
        "slug": "binalattas",
        "name": "Binalavotas",
    },
    {
        "slug": "binapenta-pkk",
        "name": "Binapenta & PKK",
    },
    {
        "slug": "phi-jsk",
        "name": "PHI - JSK",
    },
    {
        "slug": "binwasnaker-k3",
        "name": "Binwasnaker & K3",
    },
]

def strip_trailing_punctuation(text):
    if not text:
        return ""
    lines = str(text).splitlines()
    cleaned = []
    for l in lines:
        c = re.sub(r'[\s,;:!?\-–—_/\t|*•·+~="\'\\`^]+$', '', l).strip()
        if not re.search(r'\b[A-Za-z]{1,4}\.$', c):
            c = re.sub(r'\.+$', '', c).strip()
        cleaned.append(c)
    return "\n".join(cleaned).strip()

def expand_kemnaker_position(pos):
    if not pos:
        return ""
    s = str(pos).strip()
    s = strip_trailing_punctuation(s)

    # 1. Sesditjen / Sesitjen / Sesbadan prefixes
    s = re.sub(r'\bSesditjen\b', 'Sekretaris Direktorat Jenderal', s, flags=re.IGNORECASE)
    s = re.sub(r'\bSesitjen\b', 'Sekretaris Inspektorat Jenderal', s, flags=re.IGNORECASE)
    s = re.sub(r'\bSesbadan\b', 'Sekretaris Badan', s, flags=re.IGNORECASE)

    # 2. Specific Ditjen / Unit abbreviations
    s = re.sub(
        r'\b(?:Sekretaris\s+)?(?:Ditjen|Direktorat Jenderal)\s+(?:Binapenta\s*&\s*PKK|Binapenta\s+dan\s+PKK|Binapenta)\b',
        lambda m: ('Sekretaris ' if 'sekretaris' in m.group(0).lower() else '') + 
                  'Direktorat Jenderal Pembinaan Penempatan Tenaga Kerja dan Perluasan Kesempatan Kerja',
        s, flags=re.IGNORECASE
    )
    s = re.sub(
        r'\b(?:Sekretaris\s+)?(?:Ditjen|Direktorat Jenderal)\s+(?:PHI\s*[-–—]\s*JSK|PHI\s*&\s*JSK|PHI\s+dan\s+JSK|PHI)\b',
        lambda m: ('Sekretaris ' if 'sekretaris' in m.group(0).lower() else '') + 
                  'Direktorat Jenderal Pembinaan Hubungan Industrial dan Jaminan Sosial Tenaga Kerja',
        s, flags=re.IGNORECASE
    )
    s = re.sub(
        r'\b(?:Sekretaris\s+)?(?:Ditjen|Direktorat Jenderal)\s+(?:Binalavotas|Binalattas)\b',
        lambda m: ('Sekretaris ' if 'sekretaris' in m.group(0).lower() else '') + 
                  'Direktorat Jenderal Pembinaan Pelatihan Vokasi dan Produktivitas',
        s, flags=re.IGNORECASE
    )
    s = re.sub(
        r'\b(?:Sekretaris\s+)?(?:Ditjen|Direktorat Jenderal)\s+(?:Binwasnaker\s*&\s*K3|Binwasnaker\s+dan\s+K3|Binwasnaker)\b',
        lambda m: ('Sekretaris ' if 'sekretaris' in m.group(0).lower() else '') + 
                  'Direktorat Jenderal Pembinaan Pengawasan Ketenagakerjaan dan Keselamatan dan Kesehatan Kerja',
        s, flags=re.IGNORECASE
    )

    # 3. Barenbang
    s = re.sub(
        r'\bSekretaris\s+Barenbang\b',
        'Sekretaris Badan Perencanaan dan Pengembangan Ketenagakerjaan',
        s, flags=re.IGNORECASE
    )
    s = re.sub(
        r'\bKepala\s+Barenbang\b',
        'Kepala Badan Perencanaan dan Pengembangan Ketenagakerjaan',
        s, flags=re.IGNORECASE
    )

    # 4. Biro Humas -> Biro Hubungan Masyarakat
    s = re.sub(r'\bBiro\s+Humas\b', 'Biro Hubungan Masyarakat', s, flags=re.IGNORECASE)

    # 5. Remaining Ditjen / Setjen / Itjen standalone words
    s = re.sub(r'\bDitjen\b', 'Direktorat Jenderal', s, flags=re.IGNORECASE)
    s = re.sub(r'\bSetjen\b', 'Sekretariat Jenderal', s, flags=re.IGNORECASE)
    s = re.sub(r'\bItjen\b', 'Inspektorat Jenderal', s, flags=re.IGNORECASE)

    # 6. Normalize Menteri & Wakil Menteri
    if s.lower() == 'wakil menteri ketenagakerjaan':
        s = 'Wakil Menteri Ketenagakerjaan Republik Indonesia'
    elif s.lower() == 'menteri ketenagakerjaan':
        s = 'Menteri Ketenagakerjaan Republik Indonesia'

    s = re.sub(r'\s+', ' ', s).strip()
    return s

def is_valid_official_name(name):
    if not name:
        return False
    s = strip_trailing_punctuation(str(name).strip())
    if not s:
        return False
    # If string contains no alphanumeric characters (e.g. "-", "---", "- . -", etc.)
    if not re.search(r'[A-Za-z0-9]', s):
        return False
    if s.lower() in ("kosong", "belum ada", "vacant", "nihil", "n/a", "none", "null", "plt", "plt.", "plh", "plh.", "pj", "pj."):
        return False
    return True

def get_cache_file_path():
    if is_frozen():
        cache_dir = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
            "NameTableGenerator"
        )
        os.makedirs(cache_dir, exist_ok=True)
        return os.path.join(cache_dir, "kemnaker_org_cache.json")
    if os.environ.get("VERCEL"):
        import tempfile
        return os.path.join(tempfile.gettempdir(), "kemnaker_org_cache.json")
    return os.path.join(base_dir(), "kemnaker_org_cache.json")

def get_fallback_file_path():
    return resource_path("all_units_cache.json")

def format_date_id(dt_str):
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str)
        wib = timezone(timedelta(hours=7))
        if dt.tzinfo is None:
            if os.environ.get("VERCEL") or dt.hour < 7:
                dt = dt.replace(tzinfo=timezone.utc).astimezone(wib)
        else:
            dt = dt.astimezone(wib)
        bulan = [
            "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"
        ]
        time_str = dt.strftime('%H:%M')
        return f"{dt.day} {bulan[dt.month]} {dt.year}, {time_str} WIB"
    except Exception:
        return dt_str[:10]

def get_official_rank(pos, slug):
    """
    Ranks officials according to official SOTK Kemnaker RI organization chart:
    - Leader (Menteri / Dirjen / Irjen / Ka Badan / Sesjen) is always index 0.
    - Right after Leader, the Secretary (Sekretaris Ditjen / Sesitjen / Sesbadan / Sesjen / Wamen) ALWAYS comes next.
    - Followed by Directors / Inspectors / Bureau Heads / Center Heads.
    - Followed by Heads of Large Centers / Centers / Expert Staff.
    """
    p = (pos or "").lower()
    if slug == "menteri-ketenagakerjaan":
        if "wakil menteri" in p:
            return 1
        if "sekretaris jenderal" in p or "sesjen" in p:
            return 2
        if "inspektur jenderal" in p:
            return 3
        if "direktur jenderal" in p:
            return 4
        if "kepala badan" in p:
            return 5
        if "staf ahli" in p:
            return 6
        return 10

    # For Ditjen, Itjen, Barenbang, Setjen:
    # 1. Any Sekretaris (Sesditjen, Sesitjen, Sesbadan, Sekretaris)
    if any(k in p for k in ["sekretaris", "sesditjen", "sesitjen", "sesbadan"]):
        return 1
    # 2. Direktur, Inspektur, Kepala Biro, Kepala Pusat
    if any(k in p for k in ["direktur", "inspektur", "kepala biro", "kepala pusat"]):
        return 2
    # 3. Kepala Balai Besar, Kepala Sekretariat
    if any(k in p for k in ["kepala balai besar", "kepala sekretariat"]):
        return 3
    # 4. Kepala Balai
    if "kepala balai" in p:
        return 4
    return 5

def transform_unit_data(raw_units_dict, last_updated=None):
    units_list = []
    for u in UNITS:
        slug = u["slug"]
        data = raw_units_dict.get(slug, {})
        officials = []
        clean_unit_name = re.sub(r'\s*\([^)]*\)', '', u["name"]).strip()
        
        # 1. Pimpinan Unit
        leader = data.get("leader") or {}
        leader_name = strip_trailing_punctuation((leader.get("name") or "").strip())
        leader_photo = (leader.get("photo") or "").strip()
        leader_pos = expand_kemnaker_position(leader.get("position") or clean_unit_name)
        if is_valid_official_name(leader_name):
            officials.append({
                "name": leader_name,
                "position": leader_pos,
                "photo": leader_photo,
                "is_leader": True
            })
            
        # 2. Staff / Pejabat di bawahnya
        staff_list = data.get("staff") or []
        parsed_staff = []
        for s in staff_list:
            s_name = strip_trailing_punctuation((s.get("name") or "").strip())
            s_pos = expand_kemnaker_position(s.get("position") or "")
            s_photo = (s.get("photo") or "").strip()
            
            if is_valid_official_name(s_name) and s_pos:
                parsed_staff.append({
                    "name": s_name,
                    "position": s_pos,
                    "photo": s_photo,
                    "is_leader": False
                })
                
        # Sort staff so Sekretaris is ALWAYS right after the leader/jenderal
        parsed_staff.sort(key=lambda s: get_official_rank(s["position"], slug))
        officials.extend(parsed_staff)
                
        units_list.append({
            "slug": slug,
            "name": clean_unit_name,
            "officials": officials
        })
        
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "success": True,
        "last_updated": last_updated or now_iso,
        "date_formatted": format_date_id(last_updated or now_iso),
        "units": units_list
    }

def fetch_from_kemnaker_portal():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*"
    }
    
    scraped_units = {}
    for u in UNITS:
        slug = u["slug"]
        clean_unit_name = re.sub(r'\s*\([^)]*\)', '', u["name"]).strip()
        url = f"https://portal.kemnaker.go.id/api/v1/organizations/{slug}"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8, context=ctx) as res:
                data = json.loads(res.read().decode("utf-8"))
                node = data.get("data", {})
                top_name = strip_trailing_punctuation((node.get("name") or "").strip())
                top_pos = expand_kemnaker_position((node.get("job_title") or "").strip())
                top_photo = (node.get("photo") or "").strip()
                children = node.get("childrens", [])
                
                child_list = []
                def extract_children(items):
                    for c in items:
                        c_name = strip_trailing_punctuation((c.get("name") or "").strip())
                        c_pos = expand_kemnaker_position((c.get("job_title") or "").strip())
                        c_photo = (c.get("photo") or "").strip()
                        if is_valid_official_name(c_name) and c_pos:
                            child_list.append({"name": c_name, "position": c_pos, "photo": c_photo})
                        sub = c.get("childrens", [])
                        if sub:
                            extract_children(sub)
                extract_children(children)
                        
                scraped_units[slug] = {
                    "unit_name": clean_unit_name,
                    "slug": slug,
                    "leader": {
                        "name": top_name if is_valid_official_name(top_name) else "",
                        "position": top_pos,
                        "photo": top_photo
                    },
                    "staff": sorted(child_list, key=lambda s: get_official_rank(s["position"], slug))
                }
        except Exception as e:
            print(f"[Warning] Gagal fetch unit {slug}: {e}")
            
    return scraped_units

def get_kemnaker_data(force_refresh=False):
    cache_path = get_cache_file_path()
    fallback_path = get_fallback_file_path()
    
    cache_data = None
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
        except Exception:
            cache_data = None

    if not cache_data and os.path.exists(fallback_path):
        try:
            with open(fallback_path, "r", encoding="utf-8") as f:
                raw_fallback = json.load(f)
                cache_data = {
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                    "units_dict": raw_fallback
                }
        except Exception:
            cache_data = None

    is_today = False
    if cache_data and "last_updated" in cache_data:
        try:
            dt = datetime.fromisoformat(cache_data["last_updated"])
            wib = timezone(timedelta(hours=7))
            today_wib = datetime.now(wib).date()
            dt_wib = dt.astimezone(wib) if dt.tzinfo else (dt + timedelta(hours=7) if os.environ.get("VERCEL") or dt.hour < 7 else dt)
            dt_date = dt_wib.date() if hasattr(dt_wib, "date") else dt.date()
            is_today = (dt_date == today_wib)
        except Exception:
            is_today = False

    if is_today and not force_refresh and cache_data and "units_dict" in cache_data:
        return transform_unit_data(cache_data["units_dict"], cache_data.get("last_updated"))

    # Need refresh or not today
    try:
        fresh_dict = fetch_from_kemnaker_portal()
        if fresh_dict and len(fresh_dict) >= len(UNITS) // 2:
            new_cache = {
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "units_dict": fresh_dict
            }
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(new_cache, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"[Warning] Gagal menulis cache file: {e}")
            return transform_unit_data(fresh_dict, new_cache["last_updated"])
    except Exception as e:
        print(f"[Warning] Gagal memperbarui data Kemnaker: {e}")

    # If fetch failed, return what we have in cache
    if cache_data and "units_dict" in cache_data:
        return transform_unit_data(cache_data["units_dict"], cache_data.get("last_updated"))

    return {
        "success": False,
        "error": "Gagal mengambil data struktur Kemnaker RI.",
        "units": []
    }
