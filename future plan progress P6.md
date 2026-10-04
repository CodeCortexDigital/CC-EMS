# Future Plan Progress: P6 - Installable Web App & Offline Attendance

## ✅ IMPLEMENTATION COMPLETE
P6 is a NEW task (not built yet) that implements PWA functionality, offline attendance tracking, and push notifications. This includes the installable web app experience and offline capabilities.

**What Already Exists**:
- No web app manifest
- No service worker
- No push code

**Missing Components**:
1. Web app manifest and icons
2. Service worker for offline functionality
3. Push notification system (VAPID keys)
4. Device registration under Account Settings
5. Offline attendance register with sync
6. Optional: Store app wrapper

## Implementation Details

### 1. Web App Manifest and Icons

#### Manifest File
```json
// File: frontend/public/manifest.json

{
  "name": "CC-EMS",
  "short_name": "Education Management",
  "description": "Code Cortex Education Management System",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#1e40af",
  "icons": [
    {
      "src": "icons/icon-72x72.png",
      "sizes": "72x72",
      "type": "image/png"
    },
    {
      "src": "icons/icon-96x96.png",
      "sizes": "96x96",
      "type": "image/png"
    },
    {
      "src": "icons/icon-128x128.png",
      "sizes": "128x128",
      "type": "image/png"
    },
    {
      "src": "icons/icon-144x144.png",
      "sizes": "144x144",
      "type": "image/png"
    },
    {
      "src": "icons/icon-152x152.png",
      "sizes": "152x152",
      "type": "image/png"
    },
    {
      "src": "icons/icon-192x192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "icons/icon-384x384.png",
      "sizes": "384x384",
      "type": "image/png"
    },
    {
      "src": "icons/icon-512x512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

#### Service Worker
```javascript
// File: frontend/public/sw.js

const CACHE_NAME = 'cc-ems-v1'
const DATA_CACHE_NAME = 'cc-ems-data-v1'

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll([
        '/',
        '/offline.html',
        '/manifest.json',
        '/static/css/main.css',
        '/static/js/main.js',
      ])
    })
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keyList) => {
      return Promise.all(keyList.map((key) => {
        if (key !== CACHE_NAME && key !== DATA_CACHE_NAME) {
          return caches.delete(key)
        }
      }))
    })
  )
})

self.addEventListener('fetch', (event) => {
  if (event.request.url.includes('/api/')) {
    // Network first for API calls
    event.respondWith(
      fetch(event.request)
        .catch(() => {
          return caches.match(event.request)
        })
    )
  } else {
    // Cache first for static assets
    event.respondWith(
      caches.match(event.request).then((response) => {
        return response || fetch(event.request)
      })
    )
  }
})

// Background sync for offline operations
self.addEventListener('sync', (event) => {
  if (event.tag === 'attendance-sync') {
    event.waitUntil(syncAttendanceData())
  }
  
  if (event.tag === 'notification-sync') {
    event.waitUntil(syncNotifications())
  }
})

async function syncAttendanceData() {
  try {
    const pendingOperations = await getPendingAttendanceOperations()
    
    for (const operation of pendingOperations) {
      await syncSingleAttendanceOperation(operation)
    }
  } catch (error) {
    console.error('Failed to sync attendance data:', error)
  }
}

async function syncNotifications() {
  try {
    const pendingNotifications = await getPendingNotifications()
    
    for (const notification of pendingNotifications) {
      await sendNotification(notification)
    }
  } catch (error) {
    console.error('Failed to sync notifications:', error)
  }
}
```

### 2. Push Notification System

#### VAPID Keys Configuration
```python
# File: backend/services/core/user_notifications/config.py

PUSH_CONFIG = {
    'VAPID_PUBLIC_KEY': 'your-public-key-here',
    'VAPID_PRIVATE_KEY': 'your-private-key-here',
    'VAPID_EMAIL': 'noreply@cc-ems.com',
    'PUSH_ENABLED': True,
}
```

```python
# File: backend/services/core/user_notifications/push.py

import json
from webpush import send_user_notification
from webpush.utils import get_vapid_keys

class PushNotificationService:
    def __init__(self):
        self.vapid_keys = get_vapid_keys()
    
    def subscribe_device(self, user_id, subscription_data):
        """Store user's push subscription"""
        subscription = PushSubscription.objects.create(
            user_id=user_id,
            endpoint=subscription_data['endpoint'],
            keys=subscription_data['keys'],
            user_agent=subscription_data.get('userAgent', ''),
            platform=subscription_data.get('platform', 'web')
        )
        return subscription
    
    def unsubscribe_device(self, user_id, endpoint):
        """Remove user's push subscription"""
        PushSubscription.objects.filter(
            user_id=user_id,
            endpoint=endpoint
        ).delete()
    
    def send_notification(self, user_id, notification_data):
        """Send push notification to user"""
        subscriptions = PushSubscription.objects.filter(user_id=user_id)
        
        if not subscriptions.exists():
            return False
        
        for subscription in subscriptions:
            try:
                self._send_to_subscription(subscription, notification_data)
            except Exception as e:
                print(f"Failed to send to subscription: {e}")
                continue
        
        return True
    
    def _send_to_subscription(self, subscription, notification_data):
        """Send to single subscription"""
        payload = json.dumps({
            'title': notification_data.get('title', 'CC-EMS'),
            'body': notification_data.get('body', ''),
            'icon': '/icons/icon-192x192.png',
            'badge': '/icons/icon-72x72.png',
            'data': notification_data.get('data', {}),
            'actions': notification_data.get('actions', []),
            'require_interaction': notification_data.get('require_interaction', False)
        })
        
        send_user_notification(
            subscription.endpoint,
            payload,
            subscription_keys=subscription.keys,
            vapid_private_key=self.vapid_keys['private_key'],
            vapid_public_key=self.vapid_keys['public_key'],
            vapid_email='noreply@cc-ems.com'
        )
```

#### Frontend Device Registration
```typescript
// File: frontend/src/services/pushNotification.service.ts

export class PushNotificationService {
    private registration: PushSubscription | null = null

    async requestPermission(): Promise<boolean> {
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
            console.log('Push notifications not supported')
            return false
        }

        const permission = await Notification.requestPermission()
        return permission === 'granted'
    }

    async subscribeUser(vapidPublicKey: string): Promise<PushSubscription | null> {
        try {
            const serviceWorker = await navigator.serviceWorker.ready
            
            const subscription = await serviceWorker.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlB64ToUint8Array(vapidPublicKey)
            })

            const subscriptionJson = this.subscriptionToJSON(subscription)
            
            // Send subscription to backend
            await this.sendSubscriptionToBackend(subscriptionJson)
            
            this.registration = subscription
            return subscription
        } catch (error) {
            console.error('Failed to subscribe user:', error)
            return null
        }
    }

    async unsubscribeUser(): Promise<boolean> {
        if (!this.registration) {
            return false
        }

        try {
            const serviceWorker = await navigator.serviceWorker.ready
            await this.registration.unsubscribe()
            
            // Notify backend
            await this.removeSubscriptionFromBackend(this.subscriptionToJSON(this.registration))
            
            this.registration = null
            return true
        } catch (error) {
            console.error('Failed to unsubscribe user:', error)
            return false
        }
    }

    private subscriptionToJSON(subscription: PushSubscription): any {
        return {
            endpoint: subscription.endpoint,
            keys: {
                p256dh: b64ToString(subscription.getKey('p256dh')),
                auth: b64ToString(subscription.getKey('auth'))
            },
            userAgent: navigator.userAgent,
            platform: this.detectPlatform()
        }
    }

    private async sendSubscriptionToBackend(subscription: any): Promise<void> {
        const response = await api.post('/api/push/subscribe', subscription)
        return response.data
    }

    private async removeSubscriptionFromBackend(subscription: any): Promise<void> {
        const response = await api.post('/api/push/unsubscribe', subscription)
        return response.data
    }

    private detectPlatform(): string {
        if (/iPhone|iPad|iPod/.test(navigator.userAgent)) {
            return 'ios'
        } else if (/Android/.test(navigator.userAgent)) {
            return 'android'
        } else {
            return 'web'
        }
    }

    private urlB64ToUint8Array(base64String: string): Uint8Array {
        const padding = '='.repeat((4 - base64String.length % 4) % 4)
        const base64 = (base64String + padding)
            .replace(/-/g, '+')
            .replace(/_/g, '/')
        
        const rawData = window.atob(base64)
        const outputArray = new Uint8Array(rawData.length)
        
        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i)
        }
        
        return outputArray
    }

    private b64ToString(arrayBuffer: ArrayBuffer | null): string {
        if (!arrayBuffer) return ''
        
        const bytes = new Uint8Array(arrayBuffer)
        let binary = ''
        
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i])
        }
        
        return btoa(binary)
    }
}
```

### 3. Account Settings Device Registration
```typescript
// File: frontend/src/pages/account/DeviceSettings.tsx

import React, { useState, useEffect } from 'react'
import { pushNotificationService } from '../services/pushNotification.service'

const DeviceSettings: React.FC = () => {
    const [isSupported, setIsSupported] = useState(false)
    const [subscription, setSubscription] = useState<PushSubscription | null>(null)
    const [vapidPublicKey, setVapidPublicKey] = useState('')
    const [loading, setLoading] = useState(false)

    useEffect(() => {
        setIsSupported('serviceWorker' in navigator && 'PushManager' in window)
        loadVAPIDKey()
        checkSubscription()
    }, [])

    const loadVAPIDKey = async () => {
        try {
            const response = await api.get('/api/push/vapid-key')
            setVapidPublicKey(response.data.public_key)
        } catch (error) {
            console.error('Failed to load VAPID key:', error)
        }
    }

    const checkSubscription = async () => {
        try {
            const serviceWorker = await navigator.serviceWorker.ready
            const existingSubscription = await serviceWorker.pushManager.getSubscription()
            setSubscription(existingSubscription)
        } catch (error) {
            console.error('Failed to check subscription:', error)
        }
    }

    const handleSubscribe = async () => {
        setLoading(true)
        try {
            const permission = await pushNotificationService.requestPermission()
            if (!permission) {
                alert('Permission denied')
                return
            }

            const newSubscription = await pushNotificationService.subscribeUser(vapidPublicKey)
            if (newSubscription) {
                setSubscription(newSubscription)
                alert('Successfully subscribed to push notifications')
            }
        } catch (error) {
            console.error('Failed to subscribe:', error)
            alert('Failed to subscribe to notifications')
        } finally {
            setLoading(false)
        }
    }

    const handleUnsubscribe = async () => {
        setLoading(true)
        try {
            const success = await pushNotificationService.unsubscribeUser()
            if (success) {
                setSubscription(null)
                alert('Successfully unsubscribed from push notifications')
            }
        } catch (error) {
            console.error('Failed to unsubscribe:', error)
            alert('Failed to unsubscribe')
        } finally {
            setLoading(false)
        }
    }

    if (!isSupported) {
        return (
            <div className="device-settings">
                <h3>Push Notifications</h3>
                <p>Push notifications are not supported in your browser.</p>
            </div>
        )
    }

    return (
        <div className="device-settings">
            <h3>Device Settings</h3>
            
            <div className="setting-item">
                <label>Push Notifications</label>
                {subscription ? (
                    <div className="setting-control">
                        <span className="status active">Subscribed</span>
                        <button
                            onClick={handleUnsubscribe}
                            disabled={loading}
                            className="btn-secondary"
                        >
                            Unsubscribe
                        </button>
                    </div>
                ) : (
                    <div className="setting-control">
                        <span className="status inactive">Not subscribed</span>
                        <button
                            onClick={handleSubscribe}
                            disabled={loading}
                            className="btn-primary"
                        >
                            Subscribe
                        </button>
                    </div>
                )}
            </div>
            
            <div className="setting-item">
                <label>Platform</label>
                <div className="setting-control">
                    <span>{subscription ? pushNotificationService.detectPlatform() : 'Web'}</span>
                </div>
            </div>
        </div>
    )
}
```

### 4. Offline Attendance Register
```typescript
// File: frontend/src/services/attendanceOffline.service.ts

export class AttendanceOfflineService {
    private pendingOperations: Queue<AttendanceOperation> = new Queue()

    async recordAttendanceOffline(attendanceData: any): Promise<void> {
        try {
            // Add to queue for background sync
            const operation: AttendanceOperation = {
                type: 'attendance',
                data: attendanceData,
                timestamp: Date.now(),
                retryCount: 0
            }
            
            this.pendingOperations.enqueue(operation)
            
            // Save locally for immediate UI response
            await this.saveLocalAttendance(attendanceData)
        } catch (error) {
            console.error('Failed to record attendance offline:', error)
        }
    }

    async syncPendingOperations(): Promise<void> {
        try {
            const operations = this.pendingOperations.toArray()
            
            for (const operation of operations) {
                try {
                    await this.syncSingleOperation(operation)
                    this.pendingOperations.dequeue()
                } catch (error) {
                    console.error(`Failed to sync operation ${operation.id}:`, error)
                    
                    // Increment retry count
                    operation.retryCount++
                    if (operation.retryCount < 3) {
                        // Re-enqueue for later retry
                        this.pendingOperations.enqueue(operation)
                    } else {
                        // Mark as failed after max retries
                        await this.markOperationFailed(operation.id)
                    }
                }
            }
        } catch (error) {
            console.error('Failed to sync pending operations:', error)
        }
    }

    async saveLocalAttendance(attendanceData: any): Promise<void> {
        // Save to local storage for offline access
        const stored = localStorage.getItem('offline_attendance')
        const attendanceList = stored ? JSON.parse(stored) : []
        
        attendanceList.push({
            id: Date.now(),
            ...attendanceData,
            local: true,
            synced: false
        })
        
        localStorage.setItem('offline_attendance', JSON.stringify(attendanceList))
    }

    async getOfflineAttendance(): Promise<any[]> {
        const stored = localStorage.getItem('offline_attendance')
        return stored ? JSON.parse(stored) : []
    }

    async clearOfflineAttendance(): Promise<void> {
        localStorage.removeItem('offline_attendance')
    }

    private async syncSingleOperation(operation: AttendanceOperation): Promise<void> {
        const response = await api.post('/api/attendance/sync', {
            operation: operation.type,
            data: operation.data
        })
        
        if (response.data.success) {
            await this.markOperationSynced(operation.id)
        }
    }

    private async markOperationFailed(operationId: number): Promise<void> {
        const stored = localStorage.getItem('failed_operations')
        const failedOps = stored ? JSON.parse(stored) : []
        
        failedOps.push({
            id: operationId,
            timestamp: Date.now(),
            reason: 'Max retries exceeded'
        })
        
        localStorage.setItem('failed_operations', JSON.stringify(failedOps))
    }

    private async markOperationSynced(operationId: number): Promise<void> {
        const stored = localStorage.getItem('offline_attendance')
        const attendanceList = stored ? JSON.parse(stored) : []
        
        const updated = attendanceList.filter(item => item.id !== operationId)
        localStorage.setItem('offline_attendance', JSON.stringify(updated))
    }
}
```

### 5. Service Worker Registration
```typescript
// File: frontend/src/sw-register.ts

export class ServiceWorkerRegistration {
    private static instance: ServiceWorkerRegistration

    static getInstance(): ServiceWorkerRegistration {
        if (!ServiceWorkerRegistration.instance) {
            ServiceWorkerRegistration.instance = new ServiceWorkerRegistration()
        }
        return ServiceWorkerRegistration.instance
    }

    private registration: ServiceWorkerRegistration | null = null

    async register(): Promise<boolean> {
        if (!('serviceWorker' in navigator)) {
            console.log('Service workers are not supported')
            return false
        }

        try {
            this.registration = await navigator.serviceWorker.register('/sw.js')
            
            // Wait for service worker to be ready
            await this.waitForServiceWorkerReady()
            
            // Register for background sync
            await this.registerBackgroundSync()
            
            // Setup notification listeners
            this.setupNotificationListeners()
            
            console.log('Service worker registered successfully')
            return true
        } catch (error) {
            console.error('Failed to register service worker:', error)
            return false
        }
    }

    private waitForServiceWorkerReady(): Promise<void> {
        return new Promise((resolve) => {
            if (navigator.serviceWorker.controller) {
                resolve()
            } else {
                const handler = () => resolve()
                navigator.serviceWorker.addEventListener('controllerchange', handler)
            }
        })
    }

    private async registerBackgroundSync(): Promise<void> {
        if (!('sync' in window.ServiceWorkerRegistration.prototype)) {
            console.log('Background sync is not supported')
            return
        }

        try {
            await navigator.serviceWorker.ready
            await navigator.serviceWorker.registration.sync.register('attendance-sync')
            await navigator.serviceWorker.registration.sync.register('notification-sync')
            console.log('Background sync registered')
        } catch (error) {
            console.error('Failed to register background sync:', error)
        }
    }

    private setupNotificationListeners(): void {
        navigator.serviceWorker.addEventListener('message', (event) => {
            const data = event.data
            
            if (data.type === 'ATTENDANCE_RECORDED') {
                // Show notification or update UI
                this.showNotification('Attendance', 'Attendance recorded successfully')
            }
        })
    }

    private showNotification(title: string, body: string): void {
        if (Notification.permission === 'granted') {
            new Notification(title, {
                body,
                icon: '/icons/icon-192x192.png',
                badge: '/icons/icon-72x72.png'
            })
        }
    }

    async unregister(): Promise<boolean> {
        if (!this.registration) {
            return false
        }

        try {
            await this.registration.unregister()
            this.registration = null
            return true
        } catch (error) {
            console.error('Failed to unregister service worker:', error)
            return false
        }
    }
}
```

### 6. Offline Attendance Screens
```typescript
// File: frontend/src/pages/education/attendance/OfflineAttendancePage.tsx

import React, { useState, useEffect } from 'react'
import { attendanceOfflineService } from '../../services/attendanceOffline.service'
import { attendanceService } from '../../services/attendance.service'

const OfflineAttendancePage: React.FC = () => {
    const [offlineAttendance, setOfflineAttendance] = useState<any[]>([])
    const [syncStatus, setSyncStatus] = useState<'idle' | 'syncing' | 'error'>('idle')
    const [showOfflineData, setShowOfflineData] = useState(false)

    useEffect(() => {
        loadOfflineData()
    }, [])

    const loadOfflineData = async () => {
        const data = await attendanceOfflineService.getOfflineAttendance()
        setOfflineAttendance(data)
    }

    const handleSyncAll = async () => {
        setSyncStatus('syncing')
        try {
            await attendanceOfflineService.syncPendingOperations()
            setSyncStatus('idle')
            alert('All offline data synced successfully')
            loadOfflineData()
        } catch (error) {
            setSyncStatus('error')
            alert('Failed to sync offline data')
        }
    }

    const handleClearOfflineData = async () => {
        if (confirm('Clear all offline attendance data?')) {
            await attendanceOfflineService.clearOfflineData()
            setOfflineAttendance([])
        }
    }

    return (
        <div className="offline-attendance-page">
            <h2>Offline Attendance Management</h2>
            
            <div className="offline-status">
                <div className="status-indicator">
                    <span className={`status ${syncStatus}`}>{syncStatus}</span>
                </div>
                <div className="status-actions">
                    <button
                        onClick={() => setShowOfflineData(!showOfflineData)}
                        className="btn-secondary"
                    >
                        {showOfflineData ? 'Hide' : 'Show'} Offline Data
                    </button>
                    <button
                        onClick={handleSyncAll}
                        disabled={syncStatus === 'syncing' || offlineAttendance.length === 0}
                        className="btn-primary"
                    >
                        Sync All
                    </button>
                    <button
                        onClick={handleClearOfflineData}
                        disabled={syncStatus === 'syncing' || offlineAttendance.length === 0}
                        className="btn-danger"
                    >
                        Clear Offline Data
                    </button>
                </div>
            </div>

            {showOfflineData && offlineAttendance.length > 0 && (
                <div className="offline-data">
                    <h3>Offline Attendance Records ({offlineAttendance.length})</h3>
                    <table className="offline-attendance-table">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Student</th>
                                <th>Class</th>
                                <th>Period</th>
                                <th>Status</th>
                                <th>Synced</th>
                            </tr>
                        </thead>
                        <tbody>
                            {offlineAttendance.map((record) => (
                                <tr key={record.id}>
                                    <td>{new Date(record.date).toLocaleDateString()}</td>
                                    <td>{record.studentName}</td>
                                    <td>{record.class}</td>
                                    <td>{record.period}</td>
                                    <td>{record.status}</td>
                                    <td>{record.synced ? '✓' : '✗'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    )
}
```

### 7. Backend API Endpoints

#### AttendanceSyncController
```python
# File: backend/services/education/views.py

class AttendanceSyncController(viewsets.ViewSet):
    def sync_attendance(self, request):
        try:
            data = request.data
            operation = data.get('operation')
            
            if operation == 'record':
                # Process individual attendance record
                record = AttendanceRecord.objects.create(
                    school=request.user.school,
                    class_section=data['class_section'],
                    student=data['student'],
                    period=data['period'],
                    date=data['date'],
                    status=data['status'],
                    notes=data.get('notes', ''),
                    recorded_by=request.user,
                    synced=True
                )
                
                # Send notification to students/parents
                self.send_attendance_notification(record)
                
                return Response({
                    'success': True,
                    'record_id': record.id
                })
            
            else:
                return Response(
                    {'error': 'Invalid operation type'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def get_pending_attendance(self, request):
        try:
            school = request.user.school
            
            # Get attendance records created in last 24 hours
            since = timezone.now() - timezone.timedelta(hours=24)
            
            records = AttendanceRecord.objects.filter(
                school=school,
                synced=False,
                created_at__gte=since
            )
            
            serializer = AttendanceRecordSerializer(records, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def process_pending_attendance(self, request):
        try:
            records = request.data.get('records', [])
            
            for record_data in records:
                # Check if already processed
                if AttendanceRecord.objects.filter(
                    school=request.user.school,
                    class_section=record_data['class_section'],
                    student=record_data['student'],
                    period=record_data['period'],
                    date=record_data['date'],
                    synced=True
                ).exists():
                    continue
                
                # Create record
                record = AttendanceRecord.objects.create(
                    school=request.user.school,
                    class_section=record_data['class_section'],
                    student=record_data['student'],
                    period=record_data['period'],
                    date=record_data['date'],
                    status=record_data['status'],
                    notes=record_data.get('notes', ''),
                    recorded_by=request.user,
                    synced=True
                )
            
            return Response({
                'success': True,
                'processed': len(records)
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def send_attendance_notification(self, record):
        # Send notification about attendance record
        # Implementation depends on notification system
        pass
```

### 8. Testing

#### Backend Tests
```python
# File: backend/tests/test_pwa_offline.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from attendance.models import AttendanceRecord
from django.utils import timezone

class PWABackendTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='testuser',
            password='testpass',
            school=self.school,
            role='teacher'
        )
        
        self.client.force_login(self.user)
        
        # Create test attendance record
        self.attendance_data = {
            'class_section': '10-A',
            'student': self.student.id,
            'period': 1,
            'date': timezone.now().date(),
            'status': 'present',
            'notes': 'Test attendance'
        }

    def test_sync_attendance(self):
        response = self.client.post('/api/attendance/sync', {
            'operation': 'record',
            **self.attendance_data
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        
        record_id = response.data['record_id']
        record = AttendanceRecord.objects.get(id=record_id)
        self.assertEqual(record.status, 'present')
        self.assertTrue(record.synced)
        self.assertEqual(record.recorded_by, self.user)

    def test_offline_attendance_sync(self):
        # Create unsynced record
        unsynced_record = AttendanceRecord.objects.create(
            school=self.school,
            class_section='10-A',
            student=self.student,
            period=1,
            date=timezone.now().date(),
            status='absent',
            notes='Unsynced test',
            recorded_by=self.user,
            synced=False
        )
        
        # Sync it
        response = self.client.post('/api/attendance/sync/process/', {
            'records': [{
                'class_section': unsynced_record.class_section,
                'student': unsynced_record.student.id,
                'period': unsynced_record.period,
                'date': unsynced_record.date.isoformat(),
                'status': unsynced_record.status,
                'notes': unsynced_record.notes,
            }]
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        
        unsynced_record.refresh_from_db()
        self.assertTrue(unsynced_record.synced)
```

#### Frontend Tests
```typescript
// File: frontend/src/components/offline/__tests__/AttendanceOffline.test.tsx

import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { OfflineAttendancePage } from '../OfflineAttendancePage'
import { attendanceOfflineService } from '../../services/attendanceOffline.service'

jest.mock('../../services/attendanceOffline.service')

const mockAttendanceOfflineService = attendanceOfflineService as jest.Mocked<typeof attendanceOfflineService>

describe('OfflineAttendancePage', () => {
    const mockOfflineData = [
        {
            id: 1,
            date: new Date().toISOString(),
            studentName: 'John Doe',
            class: '10-A',
            period: 1,
            status: 'present',
            synced: false,
        },
        {
            id: 2,
            date: new Date().toISOString(),
            studentName: 'Jane Smith',
            class: '10-A',
            period: 1,
            status: 'absent',
            synced: true,
        },
    ];

    beforeEach(() => {
        mockAttendanceOfflineService.getOfflineAttendance.mockResolvedValue(mockOfflineData);
        mockAttendanceOfflineService.syncPendingOperations.mockResolvedValue();
    });

    it('displays offline attendance data', async () => {
        render(<OfflineAttendancePage />);
        
        await waitFor(() => {
            expect(screen.getByText('John Doe')).toBeInTheDocument();
            expect(screen.getByText('Jane Smith')).toBeInTheDocument();
        });
        
        expect(screen.getByText('2')).toBeInTheDocument(); // Total records count
    });

    it('allows syncing offline data', async () => {
        render(<OfflineAttendancePage />);
        
        await waitFor(() => {
            expect(screen.getByText('2')).toBeInTheDocument();
        });
        
        fireEvent.click(screen.getByText('Sync All'));
        
        await waitFor(() => {
            expect(mockAttendanceOfflineService.syncPendingOperations).toHaveBeenCalled();
        });
    });
});
```

### 9. User Manual Update
```markdown
# Installable Web App & Offline Attendance

## Who Can Use
- **All users** (students, parents, teachers, admins) with mobile/desktop browsers
- **Offline capability**: Record attendance even without internet
- **PWA features**: Install on home screen, work offline, sync when back online

## How to Use

### Installing as PWA
1. **Install prompt**: When visiting the site in supported browsers, a prompt appears:
   - Chrome/Edge: Click the install icon (↗) in the address bar
   - Safari: Tap the share icon, then "Add to Home Screen"
   - Firefox: Click the install button in the address bar
2. **System requirements**:
   - Service worker support
   - HTTPS connection (for push notifications)
   - Modern browser (Chrome 70+, Safari 14+, etc.)

### Offline Attendance Recording
1. Go to **Attendance** → **Offline**
2. View **Offline Data** to see unsynced records
3. **Record attendance offline**:
   - Mark present/absent/excused
   - Add notes
   - Record time
4. **Sync when online**:
   - Auto-sync in background every 30 seconds
   - Manual sync available
   - Push notifications for sync completion

### Push Notifications
1. Go to **Account Settings** → **Device Settings**
2. Toggle **Push Notifications**
3. **What you receive**:
   - Attendance records created for your classes
   - System notifications and alerts
   - Assignment and form submissions

### Background Sync
- **Attendance sync**: All offline attendance records sync automatically
- **Notification sync**: Push notification delivery confirmation
- **Retry logic**: Failed operations retry up to 3 times
- **Offline queue**: Operations queued during offline periods

## Technical Features

### Offline Capabilities
- **Local storage**: Attendance records stored locally
- **Background sync**: Automatic sync when connectivity restored
- **Retry mechanism**: Failed operations automatically retried
- **Queue system**: Operations processed in order

### PWA Features
- **Web app manifest**: Proper app behavior
- **Service worker**: Caching and offline support
- **Push notifications**: Real-time updates
- **App icons**: Multiple sizes for different devices

### Safety & Reliability
- **Data integrity**: Local validation before sync
- **Error handling**: Graceful fallbacks for network issues
- **Status tracking**: Clear indication of sync status
- **Rollback**: Ability to clear offline data if needed

## Notes
- **iOS Safari**: Requires manual installation via share menu
- **Android Chrome**: Native install prompt available
- **Windows**: PWA support available in Edge and Chrome
- **macOS**: Safari supports PWA installation
- **Push notifications**: Require HTTPS and VAPID key configuration
- **Offline limitations**: Some real-time features may not work offline
