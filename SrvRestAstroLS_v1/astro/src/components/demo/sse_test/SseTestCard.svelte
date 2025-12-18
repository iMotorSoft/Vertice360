<script>
    import { onMount, onDestroy } from 'svelte';

    /**
     * @typedef {Object} LogMessage
     * @property {string} timestamp
     * @property {number} seq
     * @property {string} message
     */

    /** @type {LogMessage[]} */
    let messages = $state([]);
    /** @type {'CONNECTING' | 'ONLINE' | 'ERROR' | 'CLOSED'} */
    let status = $state('CONNECTING');
    
    /** @type {EventSource | null} */
    let eventSource = null;

    const SSE_URL = 'http://localhost:7062/api/demo/sse-test/stream';

    function connect() {
        status = 'CONNECTING';
        eventSource = new EventSource(SSE_URL);

        eventSource.onopen = () => {
            status = 'ONLINE';
            console.log('SSE Connected');
        };

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                // Prepend new message, keep max 10
                messages = [data, ...messages].slice(0, 10);
            } catch (e) {
                console.error('Error parsing SSE message:', e);
            }
        };

        eventSource.onerror = (err) => {
            console.error('SSE Error:', err);
            status = 'ERROR';
            if (eventSource) {
                eventSource.close();
            }
        };
    }

    onMount(() => {
        connect();
    });

    onDestroy(() => {
        if (eventSource) {
            eventSource.close();
        }
    });
</script>

<div class="card w-96 bg-base-100 shadow-xl mx-auto mt-10 border border-base-300">
    <div class="card-body">
        <h2 class="card-title justify-between">
            SSE Smoke Test
            <div class="badge" class:badge-success={status === 'ONLINE'} class:badge-error={status === 'ERROR'} class:badge-warning={status === 'CONNECTING'}>
                {status}
            </div>
        </h2>
        <p class="text-xs text-base-content/70">Endpoint: {SSE_URL}</p>
        
        <div class="divider my-2"></div>
        
        <h3 class="font-bold text-sm">Last 10 Messages</h3>
        <div class="h-64 overflow-y-auto bg-base-200 rounded p-2 text-xs font-mono">
            {#if messages.length === 0}
                <div class="opacity-50 text-center mt-10">Waiting for data...</div>
            {/if}
            {#each messages as msg (msg.seq)}
                <div class="mb-1 p-1 border-b border-base-300 last:border-0">
                    <span class="text-primary font-bold">#{msg.seq}</span>
                    <span class="opacity-70">[{msg.timestamp}]</span>
                    <br/>
                    <span>{msg.message}</span>
                </div>
            {/each}
        </div>
        
        <div class="card-actions justify-end mt-4">
            {#if status === 'ERROR' || status === 'CLOSED'}
                <button class="btn btn-sm btn-primary" onclick={connect}>Retry</button>
            {/if}
        </div>
    </div>
</div>
