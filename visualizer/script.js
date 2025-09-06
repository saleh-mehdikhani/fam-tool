// D3.js script to visualize the family tree

document.addEventListener('DOMContentLoaded', () => {
    console.log('[DEBUG] DOMContentLoaded event fired.');

    const container = document.getElementById('visualization-container');
    console.log('[DEBUG] Container element:', container);

    if (!container) {
        console.error('Visualization container not found');
        return;
    }

    const width = container.clientWidth;
    const height = container.clientHeight;
    console.log(`[DEBUG] Container dimensions: width=${width}, height=${height}`);

    if (width === 0 || height === 0) {
        console.error('[DEBUG] Container has zero width or height. The visualization will not be visible.');
    }

    const svg = d3.select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    const g = svg.append('g');
    console.log('[DEBUG] SVG and G elements created.');

    svg.call(d3.zoom().on("zoom", (event) => {
        g.attr('transform', event.transform);
    }));

    d3.json('data.json').then(data => {
        console.log('[DEBUG] data.json loaded successfully:', data);

        const links = data.edges.map(d => ({ source: d.from, target: d.to, type: d.type }));
        const nodes = data.nodes;
        console.log('[DEBUG] Nodes and links mapped for simulation.');

        const simulation = d3.forceSimulation(nodes)
            .force("link", d3.forceLink(links).id(d => d.id).distance(100))
            .force("charge", d3.forceManyBody().strength(-150))
            .force("center", d3.forceCenter(width / 2, height / 2));
        console.log('[DEBUG] Force simulation created.');

        const link = g.append("g")
            .attr("class", "links")
            .selectAll("line")
            .data(links)
            .enter().append("line")
            .attr("class", d => `link ${d.type}`);

        const node = g.append("g")
            .attr("class", "nodes")
            .selectAll("g")
            .data(nodes)
            .enter().append("g")
            .attr("class", "node")
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended));

        node.append("circle")
            .attr("r", 10)
            .attr("fill", "#69b3a2");

        node.append("text")
            .text(d => d.name)
            .attr("x", 12)
            .attr("y", 3)
            .attr("class", "label");
        console.log('[DEBUG] SVG nodes and links created.');

        let tickCount = 0;
        simulation.on("tick", () => {
            if (tickCount < 5) { // Log first 5 ticks
                console.log(`[DEBUG] Simulation tick ${tickCount + 1}`);
                tickCount++;
            }
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);

            node
                .attr("transform", d => `translate(${d.x},${d.y})`);
        });

        function dragstarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }

        function dragged(event, d) {
            d.fx = event.x;
            d.fy = event.y;
        }

        function dragended(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }

    }).catch(error => {
        console.error('[DEBUG] Critical error loading or processing data.json:', error);
    });
});
