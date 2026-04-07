declare global {
  interface Window {
    APP_VERSION?: string;
  }
}

export function registerServiceWorker() {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', async () => {
      try {
        const registration = await navigator.serviceWorker.register('/sw.js');
        
        registration.addEventListener('updatefound', () => {
          const newWorker = registration.installing;
          if (!newWorker) return;

          newWorker.addEventListener('statechange', () => {
            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
              window.dispatchEvent(new CustomEvent('sw-update-available'));
            }
          });
        });

        const previousVersion = sessionStorage.getItem('sw-version');
        const currentVersion = window.APP_VERSION || 'default';
        
        if (previousVersion && previousVersion !== currentVersion) {
          window.dispatchEvent(new CustomEvent('sw-version-changed', { 
            detail: { previous: previousVersion, current: currentVersion }
          }));
        }
        
        sessionStorage.setItem('sw-version', currentVersion);
      } catch {
        // Service worker registration failed - app will work without offline support
      }
    });

    navigator.serviceWorker.addEventListener('controllerchange', () => {
      window.location.reload();
    });
  }
}
