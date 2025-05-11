後端 `tool_servers` 機制的運作方式：

__1. 設定與載入：__

- `tool_servers` 的設定主要儲存在 `TOOL_SERVER_CONNECTIONS` 這個環境變數或資料庫設定中（透過 `backend/open_webui/config.py` 中的 `PersistentConfig` 機制）。

- 這個設定是一個 JSON 陣列，每個物件代表一個外部工具伺服器的連線資訊，包含：

  - `url`: 工具伺服器的基本 URL。
  - `path`: OpenAPI 規格檔案的路徑 (預設是 `openapi.json`)。
  - `auth_type`: 認證類型，可以是 `bearer` (使用 API Key) 或 `session` (使用目前使用者的 session token)。
  - `key`: 如果 `auth_type` 是 `bearer`，則為 API Key。
  - `config`: 包含 `enable` 等設定。

- 當應用程式啟動或設定更新時，`backend/open_webui/routers/tools.py` 和 `backend/open_webui/routers/configs.py` 中的 `get_tool_servers_data` 函數會被呼叫。

- `get_tool_servers_data` (位於 `backend/open_webui/utils/tools.py`) 會非同步地從每個已啟用的工具伺服器獲取其 OpenAPI 規格。

  - 它會根據 `auth_type` 構造認證標頭。
  - 支援從 JSON 或 YAML 格式的 OpenAPI 文件中載入規格。

- 獲取到的 OpenAPI 規格會被轉換成內部使用的 `specs` 格式，並儲存在 `request.app.state.TOOL_SERVERS` 中。

__2. 工具規格轉換：__

- `convert_openapi_to_tool_payload` 函數 (位於 `backend/open_webui/utils/tools.py`) 負責將標準的 OpenAPI 規格轉換成 Open WebUI 內部工具系統可以理解的格式。
- 它會遍歷 OpenAPI 中的 `paths` 和 `methods`，提取每個操作 (operation) 的 `operationId` (作為工具名稱)、`description`、以及 `parameters` (包含路徑參數、查詢參數和請求體)。
- `resolve_schema` 函數會處理 OpenAPI 中的 `$ref`，將組件 (components) 中的定義解析並內聯到參數結構中。

__3. 工具執行：__

- 當使用者在聊天中觸發一個外部工具時，系統會呼叫 `get_tools` 函數 (位於 `backend/open_webui/utils/tools.py`)。

- 如果 `tool_id` 以 `server:` 開頭，表示這是一個外部工具伺服器提供的工具。

- 系統會從 `request.app.state.TOOL_SERVERS` 中找到對應的伺服器資料和其 `specs`。

- 對於每個 `spec` (即一個工具函數)：

  - `make_tool_function` 會創建一個非同步的 `tool_function`。
  - 這個 `tool_function` 在被呼叫時，會進一步呼叫 `execute_tool_server`。

- `execute_tool_server` 函數 (位於 `backend/open_webui/utils/tools.py`) 負責實際執行對外部工具伺服器的 API 請求：

  - 它會根據 `operationId` (工具名稱) 在伺服器的 OpenAPI `paths` 中找到對應的路由路徑 (route_path) 和 HTTP 方法。
  - 它會解析傳入的參數 (`params`)，將它們分配到路徑參數 (`path_params`)、查詢參數 (`query_params`) 或請求體 (`body_params`)。
  - 構造完整的請求 URL，包括路徑參數和查詢字串。
  - 設定認證標頭 (Bearer Token 或 Session Token)。
  - 使用 `aiohttp` 非同步地發送 HTTP 請求 (GET, POST, PUT, PATCH 等)。
  - 返回外部工具伺服器的 JSON 回應。

  流程大致如下：

1. 使用者在前端介面進行操作，觸發了需要使用外部工具的功能。
2. 前端將請求發送到 Open WebUI 的後端。
3. 後端 Python 程式碼（具體來說是 `get_tools` 和 `execute_tool_server` 等相關函數）接收到請求。
4. 後端 Python 程式碼根據設定和工具的 OpenAPI 規格，構造對外部 `tool_server` 的 API 請求。
5. 後端 Python 程式碼使用 `aiohttp` 發送這個 API 請求到外部 `tool_server`。
6. 外部 `tool_server` 處理請求並返回結果給 Open WebUI 的後端。
7. Open WebUI 的後端再將處理後的結果返回給前端，或者傳遞給語言模型進行下一步處理。


__4. 認證與權限：__

- `TOOL_SERVER_CONNECTIONS` 中的 `auth_type` 和 `key` (或 session token) 用於與外部工具伺服器進行認證。
- `backend/open_webui/utils/middleware.py` 中可以看到 `tool_servers` 的元數據處理，可能與權限檢查相關。
- `backend/open_webui/routers/users.py` 中有 `direct_tool_servers` 的權限設定，表示使用者是否有直接使用工具伺服器的權限。

__總結來說：__

Open WebUI 的後端 `tool_servers` 機制允許系統整合外部的工具服務。它透過讀取這些外部服務的 OpenAPI 規格來了解它們提供的功能和所需的參數。當使用者呼叫這些外部工具時，系統會根據 OpenAPI 規格構造並發送相應的 API 請求到外部伺服器，並將結果返回給使用者或語言模型。整個過程支援不同的認證方式，以確保安全連接。

這個機制的核心在於 `backend/open_webui/utils/tools.py` 中的 `get_tool_servers_data` (用於載入和解析規格) 和 `execute_tool_server` (用於執行工具)。設定則主要由 `backend/open_webui/config.py` 管理。
