document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM completamente cargado y parseado.");

    const currentPageElement = document.body;
    let currentPage = "";
    if (currentPageElement && currentPageElement.id) {
        currentPage = currentPageElement.id;
    } else {
        currentPage = window.location.pathname.split("/").pop();
        if (currentPage === "" || currentPage === "prototipo_web" || !currentPage.includes('.html')) {
            currentPage = "indexPage"; 
        }
    }
    console.log("[DEBUG] Página actual detectada como:", currentPage);

    function addLogEntry(panel, message, type = 'info') {
        if (!panel) {
            return;
        }
        const timestamp = new Date().toLocaleTimeString();
        const entry = document.createElement('div');
        const sanitizedMessage = message.replace(/</g, "&lt;").replace(/>/g, "&gt;");
        entry.innerHTML = `<small class="text-muted me-1">${timestamp}:</small> ${sanitizedMessage}`;

        if (type === 'error') entry.classList.add('text-danger', 'fw-bold');
        if (type === 'success') entry.classList.add('text-success');
        if (type === 'warning') entry.classList.add('text-warning', 'text-dark');
        
        while (panel.childNodes.length > 30) {
            panel.removeChild(panel.firstChild);
        }
        panel.appendChild(entry);
        panel.scrollTop = panel.scrollHeight;
    }

    if (currentPage.includes('indexPage')) {
        console.log("[DEBUG] Cargando lógica para indexPage");
        const loadAndPrepareBtn = document.getElementById('load-and-prepare-btn');
        
        if (loadAndPrepareBtn) {
            console.log("[DEBUG] Botón 'load-and-prepare-btn' encontrado en index.");
            const numSimulationsInputMain = document.getElementById('num-simulations-main');
            const errorMarginInputMain = document.getElementById('error-margin-main');
            const maxStepsInputMain = document.getElementById('max-steps-main');
            const xmlFileInputDisplay = document.getElementById('xml-file-input-display');

            loadAndPrepareBtn.addEventListener('click', () => {
                console.log("[DEBUG] Clic en 'load-and-prepare-btn'");
                if (numSimulationsInputMain && errorMarginInputMain && maxStepsInputMain && xmlFileInputDisplay) {
                    localStorage.setItem('simConfig_numSimulations', numSimulationsInputMain.value);
                    localStorage.setItem('simConfig_errorMargin', errorMarginInputMain.value);
                    localStorage.setItem('simConfig_maxSteps', maxStepsInputMain.value);
                    localStorage.setItem('simConfig_fileName', xmlFileInputDisplay.value);
                    console.log("[DEBUG] Configuración guardada en localStorage:", {
                        numSim: numSimulationsInputMain.value,
                        errMargin: errorMarginInputMain.value,
                        maxSteps: maxStepsInputMain.value,
                        fileName: xmlFileInputDisplay.value
                    });
                    window.location.href = 'dashboard.html';
                } else {
                    console.error("[DEBUG] Faltan elementos de configuración en index.html para guardar en localStorage.");
                    alert("Error: No se pudieron leer todos los campos de configuración.");
                }
            });
        } else {
            console.error("[DEBUG] ERROR: Botón 'load-and-prepare-btn' NO encontrado en index.html.");
        }
    }

    if (currentPage.includes('dashboardPage')) {
        console.log("[DEBUG] Cargando lógica para dashboardPage");

        const startSimMainBtn = document.getElementById('start-sim-main-btn');
        const pauseSimMainBtn = document.getElementById('pause-sim-main-btn');
        const stepSimMainBtn = document.getElementById('step-sim-main-btn');
        const resetSimMainBtn = document.getElementById('reset-sim-main-btn');
        const viewFinalReportBtn = document.getElementById('view-final-report-btn');
        
        const statTime = document.getElementById('stat-time');
        const statMaxStepsEl = document.getElementById('stat-max-steps');
        const statOverallProgress = document.getElementById('stat-overall-progress');
        const statProgressBar = document.getElementById('stat-progress-bar');
        const statAC = document.getElementById('stat-ac');
        const statEV = document.getElementById('stat-ev');
        const statCPI = document.getElementById('stat-cpi');
        const statActiveAgents = document.getElementById('stat-active-agents');
        const eventLogPanel = document.getElementById('event-log-panel');
        const simulationSpeedRange = document.getElementById('simulation-speed');
        
        const visTasks = {
            t1: document.getElementById('task-vis-1'),
            t2: document.getElementById('task-vis-2'),
            t3: document.getElementById('task-vis-3'),
            t4: document.getElementById('task-vis-4')
        };
        const visAgents = {
            a1: document.getElementById('agent-vis-1'),
            a2: document.getElementById('agent-vis-2'),
            a3: document.getElementById('agent-vis-3')
        };
        
        const initialAgentStyles = {};
         Object.keys(visAgents).forEach(agentId => {
            if (visAgents[agentId]) {
                const agentStyle = getComputedStyle(visAgents[agentId]);
                 initialAgentStyles[agentId] = { 
                    left: agentStyle.left, 
                    top: agentStyle.top,
                    transform: 'translate(0px, 0px)' 
                };
                visAgents[agentId].style.left = initialAgentStyles[agentId].left;
                visAgents[agentId].style.top = initialAgentStyles[agentId].top;
                visAgents[agentId].style.transform = initialAgentStyles[agentId].transform;
            }
        });

        let simulationInterval;
        let currentTimeStep = 0;
        let currentOverallProgress = 0;
        let currentAC = 0;
        let currentEV = 0;
        let currentActiveAgentsCount = 0;
        let isPaused = true;
        
        const MAX_SIM_STEPS = parseInt(localStorage.getItem('simConfig_maxSteps')) || 200;
        const errorMargin = (parseInt(localStorage.getItem('simConfig_errorMargin')) || 10) / 100;
        const fileName = localStorage.getItem('simConfig_fileName') || "Software Development Plan.xml";
        if (statMaxStepsEl) statMaxStepsEl.textContent = MAX_SIM_STEPS;

        let simTaskStates = {}; 
        let simAgentStates = {}; 
        const agentBaseCostPerHour = (MAX_SIM_STEPS > 300) ? 15 + Math.random()*5 : 25 + Math.random()*10; 
        let totalEstimatedProjectCost = 0; 

        function updateTaskVisual(taskId) {
            const taskDiv = visTasks[taskId];
            if (!taskDiv || !simTaskStates[taskId]) return;
            const state = simTaskStates[taskId];
            taskDiv.classList.remove('task-pending', 'task-in-progress', 'task-completed');
            let progressBarInner = taskDiv.querySelector('.task-progress-bar-inner');
            
            if (state.status === 'pending') taskDiv.classList.add('task-pending');
            else if (state.status === 'in-progress') taskDiv.classList.add('task-in-progress');
            else if (state.status === 'completed') taskDiv.classList.add('task-completed');
            
            if(progressBarInner) progressBarInner.style.width = `${Math.min(100, Math.max(0,state.progress))}%`;
        }

        function moveAgentVisual(agentId, targetTaskId) {
            const agentDiv = visAgents[agentId];
            const agentInitialStyle = initialAgentStyles[agentId];
            if (!agentDiv || !agentInitialStyle) return;
            
            agentDiv.classList.remove('is-working');

            if (targetTaskId) {
                const targetTaskDiv = visTasks[targetTaskId];
                if (!targetTaskDiv) return;
                
                const targetRect = targetTaskDiv.getBoundingClientRect(); 
                const agentRect = agentDiv.getBoundingClientRect(); 
                const containerRect = agentDiv.offsetParent.getBoundingClientRect();

                const agentInitialCssLeft = agentInitialStyle.left;
                const agentInitialCssTop = agentInitialStyle.top;
                let agentStartX, agentStartY;

                if (agentInitialCssLeft.includes('%')) agentStartX = (parseFloat(agentInitialCssLeft) / 100) * agentDiv.offsetParent.clientWidth;
                else agentStartX = parseFloat(agentInitialCssLeft);
                if (agentInitialCssTop.includes('%')) agentStartY = (parseFloat(agentInitialCssTop) / 100) * agentDiv.offsetParent.clientHeight;
                else agentStartY = parseFloat(agentInitialCssTop);
                
                const desiredAgentX = (targetRect.left - containerRect.left) + (targetRect.width / 2) - (agentRect.width / 2);
                const desiredAgentY = (targetRect.top - containerRect.top) - agentRect.height - 5; 

                const deltaX = desiredAgentX - agentStartX;
                const deltaY = desiredAgentY - agentStartY;
                
                agentDiv.style.transform = `translate(${deltaX}px, ${deltaY}px)`;
                agentDiv.classList.add('is-working');
            } else { 
                agentDiv.style.transform = agentInitialStyle.transform; 
            }
        }
        
        function resetVisualSimulation() {
            console.log("[DEBUG] resetVisualSimulation llamada.");
            simTaskStates = {
                t1: { name: visTasks.t1?.dataset.name || "Tarea 1", progress: 0, status: 'pending', assignedAgent: null, dependenciesMet: true, estDuration: Math.max(10, 30 + Math.floor(Math.random()*10-5)), costFactor: 10 * (MAX_SIM_STEPS/200), dependencies: [] },
                t2: { name: visTasks.t2?.dataset.name || "Tarea 2", progress: 0, status: 'pending', assignedAgent: null, dependenciesMet: false, estDuration: Math.max(15, 50 + Math.floor(Math.random()*15-7)), costFactor: 15 * (MAX_SIM_STEPS/200), dependencies: ['t1'] },
                t3: { name: visTasks.t3?.dataset.name || "Tarea 3", progress: 0, status: 'pending', assignedAgent: null, dependenciesMet: true, estDuration: Math.max(12, 40 + Math.floor(Math.random()*12-6)), costFactor: 20 * (MAX_SIM_STEPS/200), dependencies: [] },
                t4: { name: visTasks.t4?.dataset.name || "Tarea 4", progress: 0, status: 'pending', assignedAgent: null, dependenciesMet: false, estDuration: Math.max(20, 60 + Math.floor(Math.random()*20-10)), costFactor: 12 * (MAX_SIM_STEPS/200), dependencies: ['t2'] }
            };
            simAgentStates = { 
                a1: { name: visAgents.a1?.dataset.name || "Agente 1", currentTask: null, capabilities: ['t1', 't2'] },
                a2: { name: visAgents.a2?.dataset.name || "Agente 2", currentTask: null, capabilities: ['t4'] },
                a3: { name: visAgents.a3?.dataset.name || "Agente 3", currentTask: null, capabilities: ['t3'] }
            };
            
            totalEstimatedProjectCost = Object.values(simTaskStates).reduce((sum, t) => sum + t.estDuration * t.costFactor * agentBaseCostPerHour * 0.8, 0); 
            console.log("[DEBUG] Costo Total Estimado del Proyecto (para EV):", totalEstimatedProjectCost);

            for (const taskId in simTaskStates) {
                if(visTasks[taskId]) updateTaskVisual(taskId);
            }
            for (const agentId in simAgentStates) {
                if(visAgents[agentId]) moveAgentVisual(agentId, null);
            }
        }

        function resetSimulationStateDashboard() {
            console.log("[DEBUG] resetSimulationStateDashboard llamada.");
            currentTimeStep = 0;
            currentOverallProgress = 0;
            currentAC = 0;
            currentEV = 0;
            currentActiveAgentsCount = 0;
            isPaused = true;
            if (simulationInterval) clearInterval(simulationInterval);
            
            resetVisualSimulation();
            updateDashboardStatsVisuals();
            
            if (eventLogPanel) addLogEntry(eventLogPanel, `Simulación para '${fileName}' reiniciada. Límite: ${MAX_SIM_STEPS} pasos.`, "info");
            if (startSimMainBtn) startSimMainBtn.disabled = false;
            if (pauseSimMainBtn) pauseSimMainBtn.disabled = true;
            if (stepSimMainBtn) stepSimMainBtn.disabled = false;
            if (viewFinalReportBtn) viewFinalReportBtn.disabled = true;
        }

        function updateDashboardStatsVisuals() {
            if(statTime) statTime.textContent = currentTimeStep;
            if(statOverallProgress) statOverallProgress.textContent = `${currentOverallProgress.toFixed(1)}%`;
            if(statProgressBar) {
                statProgressBar.style.width = `${currentOverallProgress}%`;
                statProgressBar.textContent = `${Math.round(currentOverallProgress)}%`;
                statProgressBar.setAttribute('aria-valuenow', currentOverallProgress);
            }
            if(statAC) statAC.textContent = currentAC.toFixed(2);
            if(statEV) statEV.textContent = currentEV.toFixed(2);
            if(statCPI) statCPI.textContent = currentAC > 0 ? (currentEV / currentAC).toFixed(2) : "N/A";
            if(statActiveAgents) statActiveAgents.textContent = currentActiveAgentsCount;
        }

        function checkDependencies(taskId) {
            const task = simTaskStates[taskId];
            if (!task || !task.dependencies || task.dependencies.length === 0) return true;
            return task.dependencies.every(depId => simTaskStates[depId] && simTaskStates[depId].status === 'completed');
        }

        function simulateSingleStepDashboard() {
            const allTasksCompleted = Object.values(simTaskStates).every(t => t.status === 'completed');
            if (allTasksCompleted || currentTimeStep >= MAX_SIM_STEPS) {
                if (eventLogPanel) addLogEntry(eventLogPanel, "Simulación individual completada.", "success");
                pauseSimulationDashboard();
                if (viewFinalReportBtn) viewFinalReportBtn.disabled = false;
                return;
            }

            currentTimeStep++;
            currentActiveAgentsCount = 0;

            for (const taskId in simTaskStates) { 
                if (simTaskStates[taskId]) simTaskStates[taskId].dependenciesMet = checkDependencies(taskId);
            }

            for (const agentId in simAgentStates) {
                const agentState = simAgentStates[agentId];
                const agentData = visAgents[agentId] ? visAgents[agentId].dataset : {name: agentId.toUpperCase()};

                if (agentState.currentTask === null) {
                    for (const taskId of (agentState.capabilities || [])) { 
                        const taskState = simTaskStates[taskId];
                        if (!taskState) continue;
                        const taskData = visTasks[taskId] ? visTasks[taskId].dataset : {name: taskId.toUpperCase()};

                        if (taskState.status === 'pending' && taskState.assignedAgent === null && taskState.dependenciesMet) {
                            taskState.assignedAgent = agentId;
                            taskState.status = 'in-progress';
                            agentState.currentTask = taskId;
                            if (eventLogPanel) addLogEntry(eventLogPanel, `Agente ${agentData.name} -> Tarea ${taskData.name}.`);
                            if(visTasks[taskId]) updateTaskVisual(taskId);
                            if(visAgents[agentId]) moveAgentVisual(agentId, taskId);
                            break; 
                        }
                    }
                }
            }
            
            for (const agentId in simAgentStates) {
                const agentState = simAgentStates[agentId];
                if (agentState.currentTask !== null) {
                    currentActiveAgentsCount++;
                    const taskId = agentState.currentTask;
                    const taskState = simTaskStates[taskId];
                     if (!taskState) { 
                        console.error(`[DEBUG] Agente ${agentId} asignado a tarea ${taskId} que no existe en simTaskStates.`);
                        agentState.currentTask = null; 
                        if(visAgents[agentId]) moveAgentVisual(agentId, null);
                        continue;
                    }
                    const agentData = visAgents[agentId] ? visAgents[agentId].dataset : {name: agentId.toUpperCase()};
                    const taskData = visTasks[taskId] ? visTasks[taskId].dataset : {name: taskId.toUpperCase()};
                    
                    let progressIncrement = (100 / taskState.estDuration) * (1 + (Math.random() - 0.5) * 2 * errorMargin);
                    progressIncrement = Math.max(0.1 / taskState.estDuration, progressIncrement); 
                    taskState.progress += progressIncrement;
                    taskState.progress = Math.max(0, Math.min(taskState.progress, 100));
                    if(visTasks[taskId]) updateTaskVisual(taskId);

                    if (taskState.progress >= 100) {
                        taskState.status = 'completed';
                        if (eventLogPanel) addLogEntry(eventLogPanel, `Agente ${agentData.name} COMPLETA Tarea ${taskData.name}!`, "success");
                        if(visTasks[taskId]) updateTaskVisual(taskId);
                        agentState.currentTask = null; 
                        if(visAgents[agentId]) moveAgentVisual(agentId, null); 
                    }
                }
            }

            let totalEstDurationAllTasks = 0;
            let currentWeightedProgressSum = 0;
            Object.values(simTaskStates).forEach(t => { 
                totalEstDurationAllTasks += t.estDuration; 
                currentWeightedProgressSum += (t.progress / 100) * t.estDuration; 
            });
            currentOverallProgress = totalEstDurationAllTasks > 0 ? Math.min(100, (currentWeightedProgressSum / totalEstDurationAllTasks) * 100) : (allTasksCompleted ? 100 : 0);
            
            currentAC += currentActiveAgentsCount * (agentBaseCostPerHour * (1 + (Math.random() - 0.5) * errorMargin)); 
            currentEV = (currentOverallProgress / 100) * totalEstimatedProjectCost;
            currentEV = Math.min(currentEV, currentAC * 1.5 + (totalEstimatedProjectCost * 0.05)); 
            if (currentOverallProgress < 5 && currentAC > 0) {
                currentEV = Math.min(currentEV, currentAC * 0.3);
            }
            
            updateDashboardStatsVisuals();
        }

        function startSimulationDashboard() {
            console.log("[DEBUG] startSimulationDashboard llamada. Pausado:", isPaused, "Intervalo:", simulationInterval);
            if (!isPaused && simulationInterval) {
                console.log("[DEBUG] Simulación ya corriendo, no se reinicia.");
                return;
            }
            isPaused = false;
            if (startSimMainBtn) startSimMainBtn.disabled = true;
            if (pauseSimMainBtn) pauseSimMainBtn.disabled = false;
            if (stepSimMainBtn) stepSimMainBtn.disabled = true;
            if (viewFinalReportBtn) viewFinalReportBtn.disabled = true;
            if (eventLogPanel) addLogEntry(eventLogPanel, "Simulación iniciada/reanudada...", "info");
            
            let speedValue = 5;
            if (simulationSpeedRange && simulationSpeedRange.value) {
                const parsedSpeed = parseInt(simulationSpeedRange.value);
                if (!isNaN(parsedSpeed)) speedValue = parsedSpeed;
            }
            const intervalDuration = Math.max(100, 1100 - (speedValue * 100));
            console.log("[DEBUG] Intervalo de simulación fijado a:", intervalDuration);
            simulationInterval = setInterval(simulateSingleStepDashboard, intervalDuration);
        }

        function pauseSimulationDashboard() {
            console.log("[DEBUG] pauseSimulationDashboard llamada. Pausado:", isPaused);
            if (isPaused && !simulationInterval) { 
                 console.log("[DEBUG] Simulación ya pausada y sin intervalo.");
                return;
            }
            isPaused = true;
            clearInterval(simulationInterval);
            simulationInterval = null;
            if (startSimMainBtn) startSimMainBtn.disabled = false;
            if (pauseSimMainBtn) pauseSimMainBtn.disabled = true;
            const simulationFinished = Object.values(simTaskStates).every(t => t.status === 'completed') || currentTimeStep >= MAX_SIM_STEPS;
            if (stepSimMainBtn) stepSimMainBtn.disabled = simulationFinished;
            if (viewFinalReportBtn) viewFinalReportBtn.disabled = !simulationFinished; 
            if (eventLogPanel) addLogEntry(eventLogPanel, "Simulación pausada.", "info");
            Object.keys(visAgents).forEach(agentId => { if(visAgents[agentId]) visAgents[agentId].classList.remove('is-working')});
        }
        
        if(startSimMainBtn) startSimMainBtn.addEventListener('click', startSimulationDashboard); else console.error("[DEBUG] Botón Iniciar NO encontrado en Dashboard");
        if(pauseSimMainBtn) pauseSimMainBtn.addEventListener('click', pauseSimulationDashboard); else console.error("[DEBUG] Botón Pausar NO encontrado en Dashboard");
        if(stepSimMainBtn) {
            stepSimMainBtn.addEventListener('click', () => {
                console.log("[DEBUG] Clic en Avanzar Paso.");
                if (!isPaused) {
                    if (eventLogPanel) addLogEntry(eventLogPanel, "Info: Pause la simulación para avanzar paso a paso.", "info"); return;
                }
                if (eventLogPanel) addLogEntry(eventLogPanel, "Avanzando un paso...", "info");
                simulateSingleStepDashboard();
                const simulationFinished = Object.values(simTaskStates).every(t => t.status === 'completed') || currentTimeStep >= MAX_SIM_STEPS;
                if (simulationFinished) {
                    stepSimMainBtn.disabled = true; 
                    if (viewFinalReportBtn) viewFinalReportBtn.disabled = false;
                }
            });
        } else console.error("[DEBUG] Botón Avanzar Paso NO encontrado en Dashboard");
        
        if(resetSimMainBtn) {
            resetSimMainBtn.addEventListener('click', () => {
                console.log("[DEBUG] Clic en Reiniciar Simulación.");
                if (eventLogPanel) eventLogPanel.innerHTML = ''; 
                resetSimulationStateDashboard();
            });
        } else console.error("[DEBUG] Botón Reiniciar NO encontrado en Dashboard");

        if(viewFinalReportBtn) {
            viewFinalReportBtn.addEventListener('click', () => {
                console.log("[DEBUG] Clic en Ver Reporte Final.");
                pauseSimulationDashboard(); 
                window.location.href = 'report.html'; 
            });
        } else console.error("[DEBUG] Botón Ver Reporte NO encontrado en Dashboard");
        
        resetSimulationStateDashboard(); 
        if (eventLogPanel) addLogEntry(eventLogPanel, `Dashboard listo para simular '${fileName}'. Haz clic en Iniciar.`, "info");
    }

    // --- LÓGICA PARA REPORT.HTML ---
    if (currentPage.includes('reportPage')) {
        console.log("[DEBUG] Cargando lógica para reportPage");
        const reportNumSimsEl = document.getElementById('report-num-sims');
        const summaryTableAgg = document.getElementById('summary-table-agg');
        const resultsTableBodyAgg = document.querySelector('#results-table-agg tbody');
        const downloadCsvAggBtn = document.getElementById('download-csv-agg-btn');
        const costDistributionChartCanvas = document.getElementById('costDistributionChartCanvas');
        let costDistributionChart = null;

        const numSimsForReport = parseInt(localStorage.getItem('simConfig_numSimulations')) || 10;
        const maxStepsConfig = parseInt(localStorage.getItem('simConfig_maxSteps')) || 200;
        if(reportNumSimsEl) reportNumSimsEl.textContent = numSimsForReport;

        const simulatedReportData = [];
        for (let i = 1; i <= numSimsForReport; i++) {
            const time = Math.floor(maxStepsConfig * (0.7 + Math.random() * 0.3) );
            const completion = (70 + Math.random() * 30);
            const baseCostPerStepForReport = (20 + Math.random()*10) * (3 + Math.random()*2); 
            const ac = time * baseCostPerStepForReport * (1 + (Math.random() - 0.5) * 0.4); 
            const ev = (completion / 100) * (time * baseCostPerStepForReport * (1 + (Math.random() - 0.5) * 0.2)); 
            const cpi = ac > 0 ? (ev / ac) : 0;
            simulatedReportData.push({ simId: i, time, completion, ev, ac, cpi });
        }
        
        if (summaryTableAgg) {
            const avgTime = simulatedReportData.reduce((sum, r) => sum + r.time, 0) / numSimsForReport;
            const avgCompletion = simulatedReportData.reduce((sum, r) => sum + r.completion, 0) / numSimsForReport;
            const avgEV = simulatedReportData.reduce((sum, r) => sum + r.ev, 0) / numSimsForReport;
            const avgAC = simulatedReportData.reduce((sum, r) => sum + r.ac, 0) / numSimsForReport;
            const validCpiData = simulatedReportData.filter(r => r.cpi > 0 && isFinite(r.cpi));
            const avgCPI = validCpiData.length > 0 ? validCpiData.reduce((sum, r) => sum + r.cpi, 0) / validCpiData.length : 0;


            summaryTableAgg.innerHTML = `
                <tbody>
                    <tr><td>Ejecuciones Consideradas</td><td>${numSimsForReport}</td></tr>
                    <tr><td>Promedio Pasos Finales</td><td>${avgTime.toFixed(0)}</td></tr>
                    <tr><td>Promedio Completitud Final</td><td>${avgCompletion.toFixed(1)}%</td></tr>
                    <tr><td>Promedio EV Final ($)</td><td>${avgEV.toFixed(2)}</td></tr>
                    <tr><td>Promedio AC Final ($)</td><td>${avgAC.toFixed(2)}</td></tr>
                    <tr><td>Promedio CPI Final</td><td>${avgCPI.toFixed(2)}</td></tr>
                </tbody>
            `;
        }

        if (resultsTableBodyAgg) {
            resultsTableBodyAgg.innerHTML = ''; 
            simulatedReportData.forEach(r => {
                resultsTableBodyAgg.innerHTML += `
                    <tr>
                        <td>${r.simId}</td><td>${r.time}</td><td>${r.completion.toFixed(1)}</td>
                        <td>${r.ev.toFixed(2)}</td><td>${r.ac.toFixed(2)}</td><td>${r.cpi.toFixed(2)}</td>
                    </tr>
                `;
            });
        }

        if(costDistributionChartCanvas) {
            console.log("[DEBUG] Inicializando gráfico de distribución de costos.");
            const costs = simulatedReportData.map(r => r.ac).filter(c => c > 0 && isFinite(c));
            if (costs.length > 0) {
                const minCost = Math.min(...costs);
                const maxCost = Math.max(...costs);
                const numBins = Math.min(Math.max(1, Math.floor(Math.sqrt(costs.length))), 10);
                const binSize = (maxCost - minCost > 0 && numBins > 0) ? (maxCost - minCost) / numBins : (costs.length > 0 ? costs[0]/numBins : 1); 
                const bins = Array(numBins).fill(0);
                const binLabels = [];

                if (binSize > 0 && numBins > 0) {
                     for (let i = 0; i < numBins; i++) {
                        const lowerBound = minCost + i * binSize;
                        const upperBound = minCost + (i + 1) * binSize;
                        binLabels.push(`$${Math.round(lowerBound)}-$${Math.round(upperBound)}`);
                    }
                    costs.forEach(cost => {
                        let binIndex = binSize > 0 ? Math.floor((cost - minCost) / binSize) : 0;
                        if (binIndex >= numBins) binIndex = numBins - 1; 
                        if (binIndex < 0) binIndex = 0;
                        bins[binIndex]++;
                    });
                } else if (costs.length > 0) { 
                    binLabels.push(`$${minCost.toFixed(0)}`);
                    if (bins.length > 0) bins[0] = costs.length; else bins.push(costs.length);
                }
                
                const ctx = costDistributionChartCanvas.getContext('2d');
                if(costDistributionChart) costDistributionChart.destroy();
                costDistributionChart = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: binLabels,
                        datasets: [{
                            label: 'Frecuencia de Costos Finales (AC)',
                            data: bins,
                            backgroundColor: 'rgba(255, 255, 255, 0.8)',
                            borderColor: 'rgb(0, 0, 0)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true, maintainAspectRatio: false,
                        scales: { 
                            y: { 
                                beginAtZero: true, 
                                title: { 
                                    display: true, 
                                    text: 'Número de Simulaciones',
                                    color: 'white',
                                    font: { size: 12 }
                                }, 
                                ticks: {
                                    stepSize: Math.max(1, Math.floor(Math.max(0,...bins) / 5)), 
                                    font: { size: 9 },
                                    color: 'white'
                                }
                            },
                            x: { 
                                title: {
                                    display: true, 
                                    text: 'Rangos de Costo ($)',
                                    color: 'white',
                                    font: { size: 12 }
                                }, 
                                ticks: {
                                    font: { size: 9 },
                                    color: 'white'
                                }
                            }
                        },
                        plugins: { 
                            legend: { 
                                display: true, 
                                position: 'top', 
                                labels: {
                                    font: { size: 10 },
                                    color: 'white'
                                }
                            }
                        }
                    }
                });
                 console.log("[DEBUG] Gráfico de distribución de costos dibujado.");
            } else {
                console.warn("[DEBUG] No hay datos de costo válidos para el gráfico de distribución.");
                if (costDistributionChartCanvas.parentElement) {
                     costDistributionChartCanvas.parentElement.innerHTML = "<p class='text-muted text-center mt-3'>No hay suficientes datos de costos para generar el gráfico.</p>";
                }
            }
        } else {
            console.warn("[DEBUG] Canvas para gráfico de costos NO encontrado en report.html.");
        }

        if(downloadCsvAggBtn) {
            downloadCsvAggBtn.addEventListener('click', () => {
                alert('Simulación: Descargando reporte CSV...\n(Esta es una demostración, no se descargará ningún archivo real)');
            });
        } else {
            console.warn("[DEBUG] Botón Descargar CSV NO encontrado en report.html.");
        }
    }
});