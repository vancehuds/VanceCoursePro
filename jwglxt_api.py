"""
Jwglxt Academic System API Wrapper
Generic wrapper for 正方教务系统 (jwglxt).
Handles login, course fetching, and course selection.
"""

import re
import base64
import requests
from urllib.parse import urlencode


class JwglxtAPI:
    """API wrapper for 正方教务系统 (jwglxt)."""

    DEFAULT_BASE_URL = ""  # Must be configured by user

    def __init__(self, base_url: str = None):
        self.BASE_URL = base_url if base_url else self.DEFAULT_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        self.csrf_token = None
        self.public_key = None
        self.modulus = None
        self.exponent = None
        self.student_info = {}  # Stores njdm_id, zyh_id, xkkz_id etc.
        self.login_page_url = "" # Store the exact URL with timestamp

    def _get_login_page(self):
        """Fetch login page to get CSRF token and public key."""
        import time
        timestamp = int(time.time() * 1000)
        self.login_page_url = f"{self.BASE_URL}/xtgl/login_slogin.html?time={timestamp}"
        
        resp = self.session.get(self.login_page_url)
        resp.raise_for_status()

        # Extract CSRF token
        csrf_match = re.search(r'name="csrftoken"\s+value="([^"]+)"', resp.text)
        if csrf_match:
            self.csrf_token = csrf_match.group(1)
        else:
            raise ValueError("Failed to find CSRF token on login page.")
        return resp.text

    def _get_public_key(self):
        """Fetch RSA public key for password encryption."""
        url = f"{self.BASE_URL}/xtgl/login_getPublicKey.html"
        resp = self.session.get(url)
        resp.raise_for_status()
        data = resp.json()
        self.modulus = data.get("modulus")
        self.exponent = data.get("exponent")
        if not self.modulus or not self.exponent:
            raise ValueError("Failed to get RSA public key.")

    def _encrypt_password(self, password: str) -> str:
        """Encrypt password using RSA with PKCS1 v1.5 padding."""
        import os
        
        # Decode Base64 modulus and exponent
        modulus_bytes = base64.b64decode(self.modulus)
        exponent_bytes = base64.b64decode(self.exponent)
        
        # Handle modulus length (strip leading zero if present)
        if len(modulus_bytes) == 129 and modulus_bytes[0] == 0:
            modulus_bytes = modulus_bytes[1:]
            
        key_len = len(modulus_bytes) # Should be 128 for 1024-bit key
        
        n = int.from_bytes(modulus_bytes, 'big')
        e = int.from_bytes(exponent_bytes, 'big')

        # Prepare message
        message = password.encode('utf-8')
        
        # PKCS#1 v1.5 Padding: 00 02 [PS] 00 [Message]
        # PS is random non-zero bytes
        # Length of PS = key_len - len(message) - 3
        
        if len(message) > key_len - 11:
            raise ValueError("Message too long for RSA key")
            
        pad_len = key_len - len(message) - 3
        
        # Generate random non-zero padding
        padding = b""
        while len(padding) < pad_len:
            byte = os.urandom(1)
            if byte != b'\x00':
                padding += byte
                
        # Construct block
        # Note: The leading 00 is represented by ensuring the integer is less than modulus,
        # effectively implicit when converting bytes to int.
        # But for correctness in 'block' construction:
        block = b'\x00\x02' + padding + b'\x00' + message
        
        m = int.from_bytes(block, 'big')
        
        # Encrypt
        c = pow(m, e, n)
        
        # Convert to bytes
        encrypted_bytes = c.to_bytes(key_len, 'big')
        
        # Encode as Base64
        encrypted_base64 = base64.b64encode(encrypted_bytes).decode('ascii')
        return encrypted_base64

    def login(self, username: str, password: str) -> bool:
        """
        Perform login.
        Returns True on success, raises exception on failure.
        """
        self._get_login_page()
        self._get_public_key()

        encrypted_password = self._encrypt_password(password)

        import time
        timestamp = int(time.time() * 1000)  # milliseconds
        url = f"{self.BASE_URL}/xtgl/login_slogin.html?time={timestamp}"
        data = {
            "csrftoken": self.csrf_token,
            "language": "zh_CN",
            "ydType": "",
            "yhm": username,
            "mm": encrypted_password,
        }
        
        # Add headers that match the browser request
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": self.login_page_url,
            "Upgrade-Insecure-Requests": "1",
        }
        
        resp = self.session.post(url, data=data, headers=headers, allow_redirects=True)
        resp.raise_for_status()

        # Check if login was successful by looking at the final URL after redirects
        # Successful login will redirect to index_initMenu or similar
        # Failed login will stay on login_slogin.html
        final_url = resp.url
        
        if 'login_slogin' in final_url or 'login' in final_url.split('/')[-1]:
            # Still on login page, check for error message
            error_match = re.search(r'id="tips"\\s*[^>]*>([^<]+)<', resp.text)
            if error_match:
                error_msg = error_match.group(1).strip()
            else:
                error_msg = "用户名或密码不正确"
            raise ValueError(f"Login failed: {error_msg}")
        
        # Check if we reached a valid page (index, menu, etc.)
        if 'index' in final_url or 'menu' in final_url or len(resp.text) > 1000:
            return True
        
        # If we're here, something unexpected happened
        raise ValueError(f"Login failed: Unexpected redirect to {final_url}")

    def init_course_selection(self, gnmkdm: str = "N253512") -> dict:
        """
        Initialize course selection page.
        Returns student info parameters needed for subsequent requests.
        """
        url = f"{self.BASE_URL}/xsxk/zzxkyzb_cxZzxkYzbIndex.html?gnmkdm={gnmkdm}&layout=default"
        resp = self.session.get(url)
        resp.raise_for_status()

        # Extract all input fields (hidden or otherwise) to capture necessary params
        inputs = re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', resp.text)
        for name, value in inputs:
            self.student_info[name] = value

        # Extract xkkz_id (course selection context ID)
        # Check if xkkz_id is empty in scraped data, if so, look for overrides
        if not self.student_info.get('xkkz_id'):
             # Try firstXkkzId
            xkkz_match = re.search(r'id="firstXkkzId"\s+value="([^"]*)"', resp.text)
            if xkkz_match:
                self.student_info['xkkz_id'] = xkkz_match.group(1)

        # Extract others if empty
        if not self.student_info.get('njdm_id'):
            njdm_match = re.search(r'id="firstNjdmId"\s+value="([^"]+)"', resp.text)
            if njdm_match:
                 self.student_info['njdm_id'] = njdm_match.group(1)

        if not self.student_info.get('zyh_id'):
            zyh_match = re.search(r'id="firstZyhId"\s+value="([^"]+)"', resp.text)
            if zyh_match:
                 self.student_info['zyh_id'] = zyh_match.group(1)
        
        if not self.student_info.get('kklxdm'):
            kklxdm_match = re.search(r'id="firstKklxdm"\s+value="([^"]+)"', resp.text)
            if kklxdm_match:
                 self.student_info['kklxdm'] = kklxdm_match.group(1)
                 
        # Extract all available tabs
        # pattern: onclick="queryCourse\(this,'(\w+)','(\w+)','\d+','\w+'\)"[^>]*>([^<]+)</a>
        self.student_info['tabs'] = []
        # Modified regex to capture the 3rd argument which is likely rwlx
        tabs = re.findall(r"queryCourse\(this,'([^']+?)','([^']+?)','([^']+?)','[^']+?'\)[^>]*>([^<]+?)</a>", resp.text)
        for t in tabs:
            self.student_info['tabs'].append({
                'kklxdm': t[0],
                'xkkz_id': t[1],
                'rwlx': t[2],
                'name': t[3].strip()
            })

        return self.student_info

    def get_course_list(self, gnmkdm: str = "N253512", filter_name: str = None, page: int = 1, limit: int = 10) -> list:
        """
        Get list of available courses.
        Returns list of course dicts.
        """
        # Correct URL for course listing is PartDisplay, not Display
        url = f"{self.BASE_URL}/xsxk/zzxkyzb_cxZzxkYzbPartDisplay.html?gnmkdm={gnmkdm}"
        
        # Calculate pagination
        kspage = (page - 1) * limit + 1
        jspage = page * limit

        # Defaults based on successful HAR request (getmorecourse.har)
        defaults = {
            'rwlx': '2', 'xklc': '1', 'xkly': '0', 'bklx_id': '0', 'sfkkjyxdxnxq': '0',
            'kzkcgs': '0', 'xqh_id': '1', 'jg_id': '28', 
            'gnjkxdnj': '0', 'zyfx_id': 'wfx', 'kzybkxy': '0',
            'bjgkczxbbjwcx': '0', 'xbm': '1', 'xslbdm': '421', 'mzm': '01', 
            'xz': '4', 'ccdm': '3', 'xsbj': '1', 'sfkknj': '0', 'sfkkzy': '0', 
            'sfznkx': '0', 'zdkxms': '0', 'sfkxq': '1', 'sfkcfx': '0', 
            'kkbk': '0', 'kkbkdj': '0', 'bklbkcj': '0', 'sfkgbcx': '0', 'sfrxtgkcxd': '1', 
            'tykczgxdcs': str(limit), 
            'xkxnm': self.student_info.get('xkxnm', '2025'),
            'xkxqm': self.student_info.get('xkxqm', '12'), 
            'bbhzxjxb': '0', 'rlkz': '0', 'xkzgbj': '0',
            'kspage': str(kspage), 'jspage': str(jspage), 'jxbzb': ''
        }
        
        # Start with defaults
        data = defaults.copy()
        
        # Overwrite with student info (scraped values) if they exist
        for k, v in self.student_info.items():
            if v: # Only use non-empty scraped values
                data[k] = v
                
        # Handle special duplicate params that seem required
        data['njdm_id_1'] = data.get('njdm_id', '2024')
        data['zyh_id_1'] = data.get('zyh_id', '')
        # bh_id should come from student_info after init_course_selection
             
        # Ensure critical overrides - these MUST not be overwritten by scraped values
        data.update({
            "kklxdm": self.student_info.get('kklxdm', '10'),
            "xszxzt": "1",
            # Ensure pagination is correct - override any stale scraped values
            "kspage": str(kspage),
            "jspage": str(jspage),
            "tykczgxdcs": str(limit)
        })

        if filter_name:
            data["filter_list[0]"] = filter_name

        # Ensure we don't send extra junk from scraper that server might hate
        # Filter data to only include keys present in our defaults + known requireds
        # Actually, let's trust the defaults list + scraped keys that MATCH defaults
        # But scraped keys might include xtParams etc.
        # HAR had these:
        valid_keys = set(defaults.keys()) | {
            'xkkz_id', 'njdm_id', 'zyh_id', 'kklxdm', 'xszxzt', 'filter_list[0]',
            'njdm_id_1', 'zyh_id_1', 'bh_id', 'time', '_t', 'rwlx'
        }
        
        # Filter payload
        final_data = {k: v for k, v in data.items() if k in valid_keys}
        
        resp = self.session.post(url, data=final_data)
        resp.raise_for_status()

        # The response is JSON with course list in 'tmpList'
        courses = []
        try:
            res_json = resp.json()
            course_list = []
            if isinstance(res_json, dict):
                course_list = res_json.get('tmpList', [])
            elif isinstance(res_json, list):
                course_list = res_json
            
            for item in course_list:
                # Map fields
                course = {
                    "kch_id": item.get('kch_id') or item.get('kch'),
                    "kcmc": item.get('kcmc'),
                    "xf": item.get('xf'),
                    "jxb_id": item.get('jxb_id'),
                    "do_jxb_id": item.get('do_jxb_id'),
                    "jsxx": item.get('jsxx'), # Teacher info
                    "sksj": item.get('sksj'), # Schedule
                    "jxdd": item.get('jxdd'), # Location
                    "kxsl": item.get('kxsl'), # Capacity left?
                    "rwlx": item.get('rwlx'),
                    "xxkbj": item.get('xxkbj', '0'), # Selected flag: "1" = selected
                }
                courses.append(course)
                
        except Exception as e:
            # Fallback or error logging - include response content for debugging
            response_preview = resp.text[:200] if resp.text else "<empty>"
            print(f"Error parsing course list JSON: {e}")
            print(f"  Response Status: {resp.status_code}")
            print(f"  Response Preview: {response_preview}")
            # Check if this might be a session expiration (login page redirect)
            if 'login' in resp.text.lower() or 'slogin' in resp.text.lower():
                print("  [WARNING] Session may have expired - detected login page in response")
                raise Exception("会话已过期，请重新登录")
            pass
            
        return courses

    def get_class_list(self, kch_id: str, gnmkdm: str = "N253512") -> list:
        """
        Get list of classes (jxb) for a specific course with detailed info.
        Returns list of class dicts with jxb_ids, location, time, etc.
        """
        url = f"{self.BASE_URL}/xsxk/zzxkyzbjk_cxJxbWithKchZzxkYzb.html?gnmkdm={gnmkdm}"
        
        # Defaults based on shoucoursedetail.har
        data = {
            "rwlx": "2", "xkly": "0", "bklx_id": "0", "sfkkjyxdxnxq": "0",
            "kzkcgs": "0", "xqh_id": "1", "jg_id": "28", 
            "zyfx_id": "wfx", "txbsfrl": "0",
            # bh_id comes from student_info 
            "xbm": "1", "xslbdm": "421", "mzm": "01", "xz": "4", "ccdm": "3", 
            "xsbj": "1", "sfkknj": "0", "gnjkxdnj": "0", "sfkkzy": "0", "kzybkxy": "0", 
            "sfznkx": "0", "zdkxms": "0", "sfkxq": "1", "sfkcfx": "0", 
            "bbhzxjxb": "0", "kkbk": "0", "kkbkdj": "0", "bklbkcj": "0", 
            "xkxnm": self.student_info.get('xkxnm', '2025'),
            "xkxqm": self.student_info.get('xkxqm', '12'),
            "xkxskcgskg": "1", 
            "rlkz": "0", "cdrlkz": "0", "rlzlkz": "1", 
            "jxbzcxskg": "0", "xklc": "1", "cxbj": "0", "fxbj": "0",
            
            # Dynamic fields
            "kch_id": kch_id,
            "xkkz_id": self.student_info.get('xkkz_id', ''),
            "njdm_id": self.student_info.get('njdm_id', ''),
            "zyh_id": self.student_info.get('zyh_id', ''),
            "kklxdm": self.student_info.get('kklxdm', '10'),
        }

        resp = self.session.post(url, data=data)
        resp.raise_for_status()

        classes = []
        try:
            result = resp.json()
            # result is a list of dicts directly
            for item in result:
                # jxbrl = total capacity (教学班容量)
                # yxzrs = remaining capacity (剩余人数)
                total_capacity = item.get("jxbrl", "")
                remaining = item.get("yxzrs", "")
                
                classes.append({
                    "jxb_ids": item.get("do_jxb_id", ""),  # The ID used for selection
                    "jxb_mc": item.get("jxbmc") or item.get("kzmc", "未命名班级"), # Class name
                    "jsxx": item.get("jsxx", ""),  # Teacher info
                    "sksj": item.get("sksj", ""),  # Schedule time
                    "jxdd": item.get("jxdd", ""),  # Location
                    "jxbrl": total_capacity,       # Total capacity
                    "yxzrs": remaining,            # Remaining capacity
                    "xkbz": item.get("xkbz", ""),  # Remarks/Notes
                    "kclbmc": item.get("kclbmc", ""), # Course Type
                    "xf": item.get("xf", ""),      # Credits
                    "year": item.get("year", ""), # Year
                    "sxbj": item.get("sxbj", ""),  # Selected flag: "1" = selected
                })
        except Exception as e:
            # Include response content for debugging
            response_preview = resp.text[:200] if resp.text else "<empty>"
            print(f"Error parsing class list: {e}")
            print(f"  Response Status: {resp.status_code}")
            print(f"  Response Preview: {response_preview}")
            # Check if this might be a session expiration (login page redirect)
            if 'login' in resp.text.lower() or 'slogin' in resp.text.lower():
                print("  [WARNING] Session may have expired - detected login page in response")
                raise Exception("会话已过期，请重新登录")
            pass
        return classes

    def select_course(self, jxb_ids: str, kch_id: str, kcmc: str, gnmkdm: str = "N253512") -> dict:
        """
        Select a course class.
        Returns response dict with success/fail status.
        """
        url = f"{self.BASE_URL}/xsxk/zzxkyzbjk_xkBcZyZzxkYzb.html?gnmkdm={gnmkdm}"
        data = {
            "jxb_ids": jxb_ids,
            "kch_id": kch_id,
            "kcmc": kcmc,
            "rwlx": "2",
            "rlkz": "0",
            "cdrlkz": "0",
            "rlzlkz": "1",
            "sxbj": "1",
            "xxkbj": "0",
            "qz": "0",
            "cxbj": "0",
            "xkkz_id": self.student_info.get('xkkz_id', ''),
            "njdm_id": self.student_info.get('njdm_id', ''),
            "zyh_id": self.student_info.get('zyh_id', ''),
            "kklxdm": self.student_info.get('kklxdm', '10'),
            "xklc": "1",
            "xkxnm": self.student_info.get('xkxnm', '2025'),
            "xkxqm": self.student_info.get('xkxqm', '12'),
            "jcxx_id": "",
        }
        resp = self.session.post(url, data=data)
        resp.raise_for_status()

        try:
            result = resp.json()
            return result
        except Exception:
            return {"flag": "-1", "msg": "Failed to parse response."}

    def drop_course(self, jxb_ids: str, kch_id: str, gnmkdm: str = "N253512") -> dict:
        """
        Drop (withdraw from) a selected course.
        Returns response dict with success/fail status.
        Success returns "1", failure returns error message.
        """
        url = f"{self.BASE_URL}/xsxk/zzxkyzb_tuikBcZzxkYzb.html?gnmkdm={gnmkdm}"
        data = {
            "kch_id": kch_id,
            "jxb_ids": jxb_ids,
            "xkxnm": self.student_info.get('xkxnm', '2025'),
            "xkxqm": self.student_info.get('xkxqm', '12'),
            "txbsfrl": "0",
        }
        resp = self.session.post(url, data=data)
        resp.raise_for_status()

        try:
            result = resp.json()
            # Log the raw result for debugging
            print(f"[DEBUG] drop_course raw response: {result}")
            # API returns "1" on success, other values indicate different states
            if result == "1" or result == 1:
                return {"flag": "1", "msg": "退选成功", "raw": result}
            elif result == "0" or result == 0:
                return {"flag": "-1", "msg": "退选失败：您可能未选择该课程", "raw": result}
            else:
                return {"flag": "-1", "msg": str(result), "raw": result}
        except Exception:
            return {"flag": "-1", "msg": "Failed to parse response."}


if __name__ == "__main__":
    # Simple test
    api = JwglxtAPI()
    print("JwglxtAPI module loaded successfully.")
