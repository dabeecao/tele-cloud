function cloudApp(initialIsLoggedIn, initialMaxUploadSizeMB) {
    return {
        isLoggedIn: initialIsLoggedIn,
        maxUploadSizeMB: initialMaxUploadSizeMB,
        password: '', 
        isLoading: false, 
        isRefreshing: false, 
        startDownload(fileId) {
            this.isPreparingDownload = true;
            
            document.cookie = "dl_started=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
            
            const iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            iframe.src = `/download/${fileId}`;
            document.body.appendChild(iframe);

            let checkCookie = setInterval(() => {
                if (document.cookie.includes('dl_started=1')) {
                    clearInterval(checkCookie);
                    this.isPreparingDownload = false;
                    this.showToast('Luồng tải xuống đã bắt đầu!', 'success');
                    
                    document.cookie = "dl_started=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                    setTimeout(() => iframe.remove(), 2000); 
                }
            }, 500);
            
            setTimeout(() => {
                if (this.isPreparingDownload) {
                    clearInterval(checkCookie);
                    this.isPreparingDownload = false;
                    iframe.remove();
                    this.showToast('Kết nối Telegram quá lâu, vui lòng thử lại sau.', 'error');
                }
            }, 15000);
        },
        async downloadSelectedBatch() {
            const fileIdsToDownload = this.selectedIds.filter(id => {
                const f = this.files.find(file => file.id === id);
                return f && !f.is_folder;
            });

            if (fileIdsToDownload.length === 0) {
                this.showToast('Vui lòng chỉ chọn các tệp tin (Chưa hỗ trợ tải cả thư mục).', 'error');
                return;
            }

            if (this.selectedIds.length !== fileIdsToDownload.length) {
                this.showToast('Đã tự động bỏ qua các thư mục trong danh sách.');
            }

            this.showToast(`Đang chuẩn bị tải ${fileIdsToDownload.length} tệp...`);

            this.isPreparingDownload = true;
            document.cookie = "dl_started=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";

            for (let i = 0; i < fileIdsToDownload.length; i++) {
                const fileId = fileIdsToDownload[i];
                
                const iframe = document.createElement('iframe');
                iframe.style.display = 'none';
                iframe.src = `/download/${fileId}`;
                document.body.appendChild(iframe);

                if (i === 0) {
                    let checkCookie = setInterval(() => {
                        if (document.cookie.includes('dl_started=1')) {
                            clearInterval(checkCookie);
                            this.isPreparingDownload = false;
                            document.cookie = "dl_started=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                        }
                    }, 500);
                    
                    setTimeout(() => { if (this.isPreparingDownload) this.isPreparingDownload = false; }, 15000);
                }

                setTimeout(() => iframe.remove(), 20000);

                if (i < fileIdsToDownload.length - 1) {
                    await new Promise(resolve => setTimeout(resolve, 1500));
                }
            }
            
            this.selectedIds = [];
        },
        files: [], 
        searchQuery: '',
        currentPage: 1,
        itemsPerPage: 15,

        get filteredFiles() {
            if (this.searchQuery.trim() === '') return this.files;
            const query = this.searchQuery.toLowerCase();
            return this.files.filter(f => f.filename.toLowerCase().includes(query));
        },

        get totalPages() {
            return Math.ceil(this.filteredFiles.length / this.itemsPerPage) || 1;
        },

        get displayedFiles() {
            const start = (this.currentPage - 1) * this.itemsPerPage;
            const end = start + this.itemsPerPage;
            return this.filteredFiles.slice(start, end);
        },
        currentPath: '/', 
        openMenuId: null,
        selectedIds: [], 
        clipboard: { action: null, ids: [] },
        
        dragOver: false, 
        uploadModal: false,
        uploadDragOver: false,
        
        uploadQueue: [], 
        isQueueMinimized: false,
        
        get isAllUploadsDone() {
            if (this.uploadQueue.length === 0) return false;
            return this.uploadQueue.every(t => t.progress === 100 || t.isCancelled);
        },

        cancelUpload(taskId) {
            let task = this.uploadQueue.find(t => t.id === taskId);
            if (task && task.progress < 100) {
                task.isCancelled = true;
                task.statusText = 'Đã hủy tải lên';
            }
        },
        toastModal: { show: false, message: '', type: 'success' },
        toastTimeout: null,
        fileInfoModal: { show: false, file: null, typeName: '', svgIcon: '', bgColor: '' },
        modal: { show: false, type: 'alert', title: '', message: '', input: '', resolve: null, isDanger: false },
        contextMenu: { show: false, x: 0, y: 0, file: null },

        init() { if (this.isLoggedIn) this.fetchFiles(false); },

        showUIModal(type, title, message = '', defaultValue = '', isDanger = false) {
            return new Promise((resolve) => {
                this.modal = { show: true, type, title, message, input: defaultValue, resolve, isDanger };
                if (type === 'prompt') {
                    setTimeout(() => { if (this.$refs.modalInput) this.$refs.modalInput.focus(); }, 100);
                }
            });
        },
        closeUIModal(result) {
            if (this.modal.resolve) this.modal.resolve(result);
            this.modal.show = false;
        },
        async customPrompt(title, defaultValue = '') { return await this.showUIModal('prompt', title, '', defaultValue); },
        async customConfirm(title, message, isDanger = false) { return await this.showUIModal('confirm', title, message, '', isDanger); },
        async customAlert(title, message) { return await this.showUIModal('alert', title, message); },

        openContextMenu(e, file) {
            if (!file) return; 
            this.contextMenu.file = file;
            let x = e.clientX; let y = e.clientY;
            if (window.innerWidth - x < 210) x = window.innerWidth - 210;
            if (window.innerHeight - y < 250) y = window.innerHeight - 250;
            this.contextMenu.x = x;
            this.contextMenu.y = y;
            this.contextMenu.show = true;
        },
        closeContextMenu() { this.contextMenu.show = false; },

        formatDate(dateString) {
            if (!dateString) return '--';
            const safeString = dateString.replace(' ', 'T') + 'Z';
            const d = new Date(safeString);
            if (isNaN(d)) return dateString;
            return d.toLocaleDateString('vi-VN') + ' ' + d.toLocaleTimeString('vi-VN', {hour: '2-digit', minute:'2-digit'});
        },
        
        async login() {
            const fd = new FormData(); fd.append('password', this.password);
            const res = await fetch('/login', { method: 'POST', body: fd });
            if (res.ok) { this.isLoggedIn = true; this.fetchFiles(); } else this.showToast('Sai mật khẩu truy cập!', 'error');
        },
        async logout() { await fetch('/logout', { method: 'POST' }); window.location.reload(); },

        getBreadcrumbs() { return this.currentPath === '/' ? [] : this.currentPath.split('/').filter(Boolean); },
        navigateToFolder(folderName) { this.currentPath = this.currentPath === '/' ? '/' + folderName : this.currentPath + '/' + folderName; this.fetchFiles(); },
        navigateToIndex(index) { this.currentPath = '/' + this.getBreadcrumbs().slice(0, index + 1).join('/'); this.fetchFiles(); },
        navigateTo(path) { this.currentPath = path; this.fetchFiles(); },

        async fetchFiles(silentLoad = false) {
            if (!silentLoad && this.files.length === 0) {
                this.isLoading = true; 
            } else {
                this.isRefreshing = true;
            }
            
            try {
                const res = await fetch(`/api/files?path=${encodeURIComponent(this.currentPath)}`);
                const data = await res.json();
                this.files = data.files;
                
                this.selectedIds = this.selectedIds.filter(id => this.files.some(f => f.id === id));

                if (!silentLoad) {
                    this.searchQuery = '';
                    this.currentPage = 1;
                } else {
                    if (this.currentPage > this.totalPages) {
                        this.currentPage = Math.max(1, this.totalPages);
                    }
                }

            } catch (e) {
                console.error('Fetch error', e);
            } finally {
                this.isLoading = false;
                this.isRefreshing = false;
            }
        },
        
        async createNewFolder() {
            const name = await this.customPrompt("Tạo thư mục mới", "");
            if (!name || name.trim() === "") return;
            
            const tempId = 'temp_' + Date.now();
            this.files.unshift({ id: tempId, filename: name.trim(), is_folder: true, size: 0, created_at: new Date().toISOString() });
            
            const fd = new FormData(); fd.append('name', name.trim()); fd.append('path', this.currentPath);
            await fetch('/api/folders', { method: 'POST', body: fd });
            
            this.fetchFiles(true); 
            this.showToast('Đã tạo: ' + name.trim());
        },

        copyToClipboard(action, idsArray) { this.clipboard = { action: action, ids: [...idsArray] }; this.selectedIds = []; },
        
        async executePaste() {
            if (this.clipboard.ids.length === 0) return;
            
            if (this.clipboard.action === 'move') {
                this.files = this.files.filter(f => !this.clipboard.ids.includes(f.id));
            }
            
            await fetch('/api/actions/paste', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: this.clipboard.action, item_ids: this.clipboard.ids, destination: this.currentPath }) });
            
            this.clipboard = { action: null, ids: [] }; 
            this.fetchFiles(true);
            this.showToast('Hoàn tất di chuyển/sao chép!');
        },
        
        async deleteBatch() {
            const confirmed = await this.customConfirm("Xóa dữ liệu", `Bạn có chắc chắn muốn xóa ${this.selectedIds.length} mục đã chọn? Không thể hoàn tác!`, true);
            if (!confirmed) return;
            
            const idsToDelete = [...this.selectedIds];
            this.files = this.files.filter(f => !idsToDelete.includes(f.id));
            this.selectedIds = [];
            
            for (let id of idsToDelete) await fetch(`/api/files/${id}`, { method: 'DELETE' });
            this.fetchFiles(true);
            this.showToast(`Đã xóa ${idsToDelete.length} mục`, 'success');
        },

        handleDrop(e) { this.dragOver = false; this.uploadFiles(Array.from(e.dataTransfer.files)); },
        handleUploadModalSelect(e) { this.uploadFiles(Array.from(e.target.files)); e.target.value = ''; this.uploadModal = false; },
        handleUploadModalDrop(e) { this.uploadDragOver = false; this.uploadModal = false; this.uploadFiles(Array.from(e.dataTransfer.files)); },
        
        async uploadFiles(fileList) {
            const maxSizeBytes = this.maxUploadSizeMB * 1024 * 1024;
            const CHUNK_SIZE = 10 * 1024 * 1024;

            for (let i = 0; i < fileList.length; i++) {
                let file = fileList[i];
                
                if (file.size > maxSizeBytes) { 
                    await this.customAlert("File quá lớn", `File "${file.name}" vượt quá giới hạn tải lên.`); 
                    continue; 
                }

                let taskId = 'task_' + Date.now() + '_' + i;
                this.uploadQueue.unshift({ id: taskId, name: file.name, progress: 0, statusText: 'Đang chuẩn bị...', isCancelled: false });
                
                const totalChunks = Math.max(1, Math.ceil(file.size / CHUNK_SIZE));
                let hasError = false;

            for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex++) {
                    if (hasError) break;
            
                    let taskObj = this.uploadQueue.find(t => t.id === taskId);
                    if (taskObj && taskObj.isCancelled) {
                        break;
                    }
                    
                    const start = chunkIndex * CHUNK_SIZE;
                    const end = Math.min(start + CHUNK_SIZE, file.size);
                    const chunk = file.slice(start, end);

                    const fd = new FormData(); 
                    fd.append('file', chunk); 
                    fd.append('filename', file.name);
                    fd.append('path', this.currentPath); 
                    fd.append('task_id', taskId);
                    fd.append('chunk_index', chunkIndex);
                    fd.append('total_chunks', totalChunks);

                    try {
                        let task = this.uploadQueue.find(t => t.id === taskId);
                        if (task && task.statusText !== 'Lỗi kết nối!') {
                            task.statusText = `Đang đẩy lên Server (${chunkIndex + 1}/${totalChunks})...`;
                        }

                        const response = await fetch('/api/upload', {
                            method: 'POST',
                            body: fd
                        });
                        
                        if (!response.ok) throw new Error("Upload failed");
                        const result = await response.json();

                        if (task) {
                            task.progress = Math.round(((chunkIndex + 1) / totalChunks) * 50);
                        }

                        if (result.status === "processing_telegram") {
                            if (task) task.statusText = 'Đang đồng bộ với Telegram...';
                            
                            let pollInterval = setInterval(async () => {
                                try { 
                                    let t = this.uploadQueue.find(x => x.id === taskId); 
                                    
                                    if (t && t.isCancelled) {
                                        clearInterval(pollInterval);
                                        return;
                                    }
                                    
                                    let pRes = await fetch(`/api/progress/${taskId}`);
                                    if (pRes.ok) { 
                                        let pData = await pRes.json(); 
                                        let t = this.uploadQueue.find(x => x.id === taskId); 
                                        
                                        if (pData.status === 'telegram' || pData.status === 'done') { 
                                            if (t) t.progress = 50 + Math.round(pData.percent / 2); 
                                        }
                                        
                                        if (pData.status === 'done') {
                                            clearInterval(pollInterval);
                                            if (t) { t.progress = 100; t.statusText = 'Hoàn tất!'; }
                                            this.fetchFiles(true);
                                        } else if (pData.status === 'error') {
                                            clearInterval(pollInterval);
                                            if (t) t.statusText = 'Lỗi Telegram: ' + (pData.message || 'Không rõ');
                                        }
                                    } 
                                } catch (e) {
                                    console.error("Lỗi khi fetch progress:", e);
                                }
                            }, 1000);
                        }
                    } catch (err) { 
                        console.error("Lỗi upload chunk:", err);
                        let task = this.uploadQueue.find(t => t.id === taskId); 
                        if(task) task.statusText = 'Lỗi kết nối!'; 
                        hasError = true;
                    }
                }
            }
        },


        async toggleShare(file) {
            const targetFile = this.files.find(f => f.id === file.id);
            if (targetFile) {
                if (targetFile.share_token) {
                    targetFile.share_token = null;
                    await fetch(`/api/files/${file.id}/share`, { method: 'DELETE' });
                    this.showToast('Đã thu hồi link Public', 'success');
                } else {
                    targetFile.share_token = 'loading...';
                    const res = await fetch(`/api/files/${file.id}/share`, { method: 'POST' });
                    const data = await res.json();
                    
                    targetFile.share_token = data.share_token;
                    targetFile.direct_token = data.direct_token; 
                    
                    this.copyShareLink(targetFile, 'regular');
                }
            }
        },
        
        copyShareLink(file, type = 'regular') {
            const link = type === 'direct' 
                ? `${window.location.origin}/dl/${file.direct_token}` 
                : `${window.location.origin}/s/${file.share_token}`;
            
            navigator.clipboard.writeText(link);
            this.showToast(`Đã copy link ${type === 'direct' ? 'Direct' : 'Chia sẻ'}!`);
        },

        showToast(msg, type = 'success') {

            this.toastModal = { show: true, message: msg, type: type };
            
            if (this.toastTimeout) clearTimeout(this.toastTimeout);
            this.toastTimeout = setTimeout(() => {
                this.toastModal.show = false;
            }, 3500);
        },
        
        async deleteFile(id) { 
            const confirmed = await this.customConfirm("Xóa dữ liệu", "Bạn có chắc chắn muốn xóa mục này?", true); 
            if (!confirmed) return; 
            
            this.files = this.files.filter(f => f.id !== id);
            
            await fetch(`/api/files/${id}`, { method: 'DELETE' }); 
            this.fetchFiles(true);
            this.showToast('Đã xóa', 'success'); 
        },
        
        async renameFile(file) { 
            const newName = await this.customPrompt('Đổi tên file/thư mục:', file.filename); 
            if (!newName || newName === file.filename) return; 
            
            const targetFile = this.files.find(f => f.id === file.id);
            if(targetFile) targetFile.filename = newName;

            const fd = new FormData(); fd.append('new_name', newName); 
            await fetch(`/api/files/${file.id}/rename`, { method: 'PUT', body: fd }); 
            this.fetchFiles(true); 
            this.showToast('Đổi tên thành công'); 
        },

        getFileTypeData(filename) {
            if (!filename) return { n: 'Không xác định', c: 'bg-slate-100 dark:bg-slate-800', i: '' };
            const ext = filename.split('.').pop().toLowerCase();
            const types = {
                'jpg': { n: 'Hình ảnh', c: 'bg-rose-100 text-rose-500 dark:bg-rose-500/20 dark:text-rose-400', i: '<i class="fa-solid fa-image text-2xl"></i>' },
                'jpeg': 'jpg', 'png': 'jpg', 'gif': 'jpg', 'webp': 'jpg', 'svg': 'jpg',
                'mp4': { n: 'Video', c: 'bg-purple-100 text-purple-500 dark:bg-purple-500/20 dark:text-purple-400', i: '<i class="fa-solid fa-film text-2xl"></i>' },
                'mov': 'mp4', 'avi': 'mp4', 'mkv': 'mp4',
                'mp3': { n: 'Âm thanh', c: 'bg-amber-100 text-amber-500 dark:bg-amber-500/20 dark:text-amber-400', i: '<i class="fa-solid fa-music text-2xl"></i>' },
                'wav': 'mp3', 'flac': 'mp3',
                'php': { n: 'Mã nguồn', c: 'bg-indigo-100 text-indigo-500 dark:bg-indigo-500/20 dark:text-indigo-400', i: '<i class="fa-solid fa-code text-2xl"></i>' },
                'js': 'php', 'html': 'php', 'css': 'php', 'py': 'php', 'json': 'php', 'sql': 'php',
                'zip': { n: 'Tệp nén', c: 'bg-orange-100 text-orange-500 dark:bg-orange-500/20 dark:text-orange-400', i: '<i class="fa-solid fa-file-zipper text-2xl"></i>' },
                'rar': 'zip', 'ipa': 'zip', 'tar': 'zip', 'gz': 'zip', '7z': 'zip', 'apk': 'zip',
                'pdf': { n: 'Tài liệu', c: 'bg-red-100 text-red-500 dark:bg-red-500/20 dark:text-red-400', i: '<i class="fa-solid fa-file-pdf text-2xl"></i>' },
                'doc': 'pdf', 'docx': 'pdf', 'xls': 'pdf', 'xlsx': 'pdf', 'txt': 'pdf'
            };
            let result = types[ext]; if (typeof result === 'string') result = types[result]; 
            return result || { n: 'Tệp tin (' + ext.toUpperCase() + ')', c: 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400', i: '<i class="fa-solid fa-file text-2xl"></i>' };
        },
        
        showFileInfo(file) {
            if (file.is_folder) return;
            const typeData = this.getFileTypeData(file.filename);
            this.fileInfoModal = { show: true, file: file, typeName: typeData.n, svgIcon: typeData.i, bgColor: typeData.c };
        },
        formatBytes(b, d=2) { if (!+b) return '0 B'; const k = 1024, i = Math.floor(Math.log(b) / Math.log(k)); return `${parseFloat((b / Math.pow(k, i)).toFixed(d))} ${['B', 'KB', 'MB', 'GB', 'TB'][i]}`; }
    }
}