/**
 * GhostFibers - Vanilla JS / WebGL2 Component
 * Ported from React Bits (https://reactbits.dev)
 */

function hexToRgb(hex) {
  const value = hex.trim().replace(/^#/, '');
  const normalized = value.length === 3 ? value.replace(/./g, channel => channel + channel) : value;
  const match = /^([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(normalized);
  if (!match) return [1, 1, 1];
  return [parseInt(match[1], 16) / 255, parseInt(match[2], 16) / 255, parseInt(match[3], 16) / 255];
}

const vertexShaderSource = `#version 300 es
in vec2 position;
void main() {
  gl_Position = vec4(position, 0.0, 1.0);
}
`;

const fragmentShaderSource = `#version 300 es
precision highp float;

uniform vec2 uResolution;
uniform float uTime;
uniform float uSpeed;
uniform float uScale;
uniform float uRotation;
uniform float uLayers;
uniform float uWaveAmplitude;
uniform float uWaveFrequency;
uniform float uWaveSpeed;
uniform float uLayerSpeed;
uniform float uTwist;
uniform float uTwistFrequency;
uniform float uTwistSpeed;
uniform float uLineFrequency;
uniform float uLineSpacing;
uniform float uLineSharpness;
uniform float uGlowFalloff;
uniform float uGlowIntensity;
uniform float uBrightness;
uniform float uBlueBoost;
uniform float uVignette;
uniform float uGrain;
uniform float uRotationSpeed;
uniform float uLightMode;
uniform vec3 uLineColor;
uniform vec3 uGlowColor;

out vec4 fragColor;

#define MAX_LAYERS 10

mat2 rotate2d(float angle) {
  float sine = sin(angle);
  float cosine = cos(angle);
  return mat2(cosine, -sine, sine, cosine);
}

float grainHash(vec2 point) {
  point = floor(point);
  float hash = 52.9829189 * fract(dot(point, vec2(0.065, 0.005)));
  return fract(hash);
}

float layeredGrain(vec2 fragmentPixel) {
  vec2 point = mod(fragmentPixel + vec2(uTime * 30.0, -uTime * 21.0), 1024.0);
  vec2 rotated = mat2(0.8, -0.5, 0.5, 0.8) * point;
  float grain = 0.0;
  grain += 0.40 * grainHash(rotated);
  grain += 0.25 * grainHash(rotated * 2.0 + 17.0);
  grain += 0.20 * grainHash(rotated * 4.0 + 47.0);
  grain += 0.10 * grainHash(rotated * 8.0 + 113.0);
  grain += 0.05 * grainHash(rotated * 16.0 + 191.0);
  return grain;
}

void main() {
  vec2 resolution = max(uResolution, vec2(1.0));
  vec2 uv = (2.0 * gl_FragCoord.xy - resolution) / resolution.y;
  float time = uTime * uSpeed;
  vec3 backdrop = mix(vec3(0.070588, 0.058824, 0.090196), vec3(1.0), step(0.5, uLightMode));
  vec3 centerTone = max(uLineColor * 0.85567 - uGlowColor * 0.06186, vec3(0.0));
  vec3 cloudTone = uLineColor * 0.19588 + uGlowColor * 0.2268;
  vec2 p = uv;
  p /= max(uScale, 0.05);
  p = rotate2d(radians(uRotation) + time * uRotationSpeed) * p;
  vec3 color = vec3(0.0);
  float fiberField = 0.0;

  for (int index = 0; index < MAX_LAYERS; index++) {
    float fi = float(index) + 1.0;
    if (fi > uLayers) break;

    p += uWaveAmplitude * sin(p.yx * fi * uWaveFrequency + time * (uWaveSpeed + fi * uLayerSpeed));

    float radius = length(p);
    float polarAngle = atan(p.y, p.x);
    polarAngle += sin(radius * uTwistFrequency - time * uTwistSpeed + fi) * uTwist;
    p = vec2(cos(polarAngle), sin(polarAngle)) * radius;

    float lines = abs(sin(p.x * (uLineFrequency + fi * uLineSpacing) + sin(p.y * 3.0 + time)));
    lines = pow(max(0.0, 1.0 - lines), uLineSharpness);
    fiberField += lines / fi;
    color += uLineColor * lines / fi;

    float glow = exp(-uGlowFalloff * abs(sin(p.x * 3.0 + time + fi)));
    color += uGlowColor * glow * uGlowIntensity / (fi * 2.0);
  }

  float center = exp(-2.2 * dot(uv, uv));
  color += centerTone * center;

  float cloud = exp(-1.5 * length(uv + vec2(sin(time * 0.3) * 0.25, cos(time * 0.25) * 0.18)));
  color += cloudTone * cloud;

  float vignette = 1.0 - smoothstep(0.35, 1.45, length(uv));
  color *= mix(1.0 - uVignette, 1.0, vignette);
  color = 1.0 - exp(-color * uBrightness);
  color.b *= uBlueBoost;

  vec3 outputColor;
  if (uLightMode > 0.5) {
    float edgeFade = mix(1.0 - uVignette, 1.0, vignette);
    float fibers = pow(smoothstep(0.12, 1.05, fiberField) * edgeFade, 1.5);
    float atmosphere = (center * 0.025 + cloud * 0.015) * edgeFade;
    vec3 fiberInk = mix(backdrop, uLineColor, 0.52);
    vec3 airColor = mix(backdrop, uGlowColor, 0.16);

    outputColor = mix(backdrop, airColor, atmosphere);
    outputColor = mix(outputColor, fiberInk, fibers * 0.3);
  } else {
    outputColor = backdrop + color;
  }

  float noise = (layeredGrain(gl_FragCoord.xy) - 0.5) * uGrain;
  outputColor = clamp(outputColor + noise, 0.0, 1.0);
  fragColor = vec4(outputColor, 1.0);
}
`;

function createShader(gl, type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    console.error('Shader compile error:', gl.getShaderInfoLog(shader));
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

function createProgram(gl, vertexSource, fragmentSource) {
  const vertexShader = createShader(gl, gl.VERTEX_SHADER, vertexSource);
  const fragmentShader = createShader(gl, gl.FRAGMENT_SHADER, fragmentSource);
  if (!vertexShader || !fragmentShader) return null;

  const program = gl.createProgram();
  gl.attachShader(program, vertexShader);
  gl.attachShader(program, fragmentShader);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    console.error('Program link error:', gl.getProgramInfoLog(program));
    gl.deleteProgram(program);
    return null;
  }
  return program;
}

function initGhostFibers(container, options = {}) {
  if (!container) return null;

  const config = {
    lineColor: options.lineColor || '#140E35',
    glowColor: options.glowColor || '#3437A0',
    speed: options.speed !== undefined ? options.speed : 0.2,
    scale: options.scale !== undefined ? options.scale : 2,
    rotation: options.rotation !== undefined ? options.rotation : 0,
    rotationSpeed: options.rotationSpeed !== undefined ? options.rotationSpeed : 0.25,
    layers: options.layers !== undefined ? options.layers : 4,
    waveAmplitude: options.waveAmplitude !== undefined ? options.waveAmplitude : 0.015,
    waveFrequency: options.waveFrequency !== undefined ? options.waveFrequency : 3,
    waveSpeed: options.waveSpeed !== undefined ? options.waveSpeed : 0.15,
    layerSpeed: options.layerSpeed !== undefined ? options.layerSpeed : 0.08,
    twist: options.twist !== undefined ? options.twist : 0.1,
    twistFrequency: options.twistFrequency !== undefined ? options.twistFrequency : 5,
    twistSpeed: options.twistSpeed !== undefined ? options.twistSpeed : 1.2,
    lineFrequency: options.lineFrequency !== undefined ? options.lineFrequency : 5,
    lineSpacing: options.lineSpacing !== undefined ? options.lineSpacing : 2,
    lineSharpness: options.lineSharpness !== undefined ? options.lineSharpness : 16,
    glowFalloff: options.glowFalloff !== undefined ? options.glowFalloff : 10,
    glowIntensity: options.glowIntensity !== undefined ? options.glowIntensity : 1.6,
    brightness: options.brightness !== undefined ? options.brightness : 2,
    blueBoost: options.blueBoost !== undefined ? options.blueBoost : 1.25,
    vignette: options.vignette !== undefined ? options.vignette : 0.8,
    grain: options.grain !== undefined ? options.grain : 0.05,
    lightMode: options.lightMode || false,
    dpr: Math.min(Math.max(options.dpr || 1, 0.5), 2),
    fps: options.fps || 60,
    paused: options.paused || false,
    className: options.className || ''
  };

  const canvas = document.createElement('canvas');
  canvas.style.width = '100%';
  canvas.style.height = '100%';
  canvas.style.display = 'block';
  canvas.setAttribute('aria-hidden', 'true');
  container.appendChild(canvas);

  const gl = canvas.getContext('webgl2', { alpha: false, antialias: false });
  if (!gl) {
    console.warn('WebGL2 not supported for GhostFibers');
    return null;
  }

  const program = createProgram(gl, vertexShaderSource, fragmentShaderSource);
  if (!program) return null;

  // Full-screen triangle
  const positionBuffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
    -1.0, -1.0,
     3.0, -1.0,
    -1.0,  3.0
  ]), gl.STATIC_DRAW);

  const vao = gl.createVertexArray();
  gl.bindVertexArray(vao);
  const positionLocation = gl.getAttribLocation(program, 'position');
  gl.enableVertexAttribArray(positionLocation);
  gl.vertexAttribPointer(positionLocation, 2, gl.FLOAT, false, 0, 0);

  // Uniform locations cache
  const uniforms = {
    uResolution: gl.getUniformLocation(program, 'uResolution'),
    uTime: gl.getUniformLocation(program, 'uTime'),
    uSpeed: gl.getUniformLocation(program, 'uSpeed'),
    uScale: gl.getUniformLocation(program, 'uScale'),
    uRotation: gl.getUniformLocation(program, 'uRotation'),
    uRotationSpeed: gl.getUniformLocation(program, 'uRotationSpeed'),
    uLayers: gl.getUniformLocation(program, 'uLayers'),
    uWaveAmplitude: gl.getUniformLocation(program, 'uWaveAmplitude'),
    uWaveFrequency: gl.getUniformLocation(program, 'uWaveFrequency'),
    uWaveSpeed: gl.getUniformLocation(program, 'uWaveSpeed'),
    uLayerSpeed: gl.getUniformLocation(program, 'uLayerSpeed'),
    uTwist: gl.getUniformLocation(program, 'uTwist'),
    uTwistFrequency: gl.getUniformLocation(program, 'uTwistFrequency'),
    uTwistSpeed: gl.getUniformLocation(program, 'uTwistSpeed'),
    uLineFrequency: gl.getUniformLocation(program, 'uLineFrequency'),
    uLineSpacing: gl.getUniformLocation(program, 'uLineSpacing'),
    uLineSharpness: gl.getUniformLocation(program, 'uLineSharpness'),
    uGlowFalloff: gl.getUniformLocation(program, 'uGlowFalloff'),
    uGlowIntensity: gl.getUniformLocation(program, 'uGlowIntensity'),
    uBrightness: gl.getUniformLocation(program, 'uBrightness'),
    uBlueBoost: gl.getUniformLocation(program, 'uBlueBoost'),
    uVignette: gl.getUniformLocation(program, 'uVignette'),
    uGrain: gl.getUniformLocation(program, 'uGrain'),
    uLightMode: gl.getUniformLocation(program, 'uLightMode'),
    uLineColor: gl.getUniformLocation(program, 'uLineColor'),
    uGlowColor: gl.getUniformLocation(program, 'uGlowColor')
  };

  let frameId = 0;
  let elapsed = 0;
  let previousTime = performance.now();
  let lastRenderTime = 0;
  let isPaused = config.paused;
  let isVisible = true;
  let isPageVisible = !document.hidden;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  function updateUniforms() {
    gl.useProgram(program);
    const lineRgb = hexToRgb(config.lineColor);
    const glowRgb = hexToRgb(config.glowColor);
    gl.uniform3f(uniforms.uLineColor, lineRgb[0], lineRgb[1], lineRgb[2]);
    gl.uniform3f(uniforms.uGlowColor, glowRgb[0], glowRgb[1], glowRgb[2]);
    gl.uniform1f(uniforms.uSpeed, config.speed);
    gl.uniform1f(uniforms.uScale, config.scale);
    gl.uniform1f(uniforms.uRotation, config.rotation);
    gl.uniform1f(uniforms.uRotationSpeed, config.rotationSpeed);
    gl.uniform1f(uniforms.uLayers, Math.min(Math.max(Math.round(config.layers), 1), 10));
    gl.uniform1f(uniforms.uWaveAmplitude, config.waveAmplitude);
    gl.uniform1f(uniforms.uWaveFrequency, config.waveFrequency);
    gl.uniform1f(uniforms.uWaveSpeed, config.waveSpeed);
    gl.uniform1f(uniforms.uLayerSpeed, config.layerSpeed);
    gl.uniform1f(uniforms.uTwist, config.twist);
    gl.uniform1f(uniforms.uTwistFrequency, config.twistFrequency);
    gl.uniform1f(uniforms.uTwistSpeed, config.twistSpeed);
    gl.uniform1f(uniforms.uLineFrequency, config.lineFrequency);
    gl.uniform1f(uniforms.uLineSpacing, config.lineSpacing);
    gl.uniform1f(uniforms.uLineSharpness, config.lineSharpness);
    gl.uniform1f(uniforms.uGlowFalloff, config.glowFalloff);
    gl.uniform1f(uniforms.uGlowIntensity, config.glowIntensity);
    gl.uniform1f(uniforms.uBrightness, config.brightness);
    gl.uniform1f(uniforms.uBlueBoost, config.blueBoost);
    gl.uniform1f(uniforms.uVignette, config.vignette);
    gl.uniform1f(uniforms.uGrain, config.grain);
    gl.uniform1f(uniforms.uLightMode, config.lightMode ? 1.0 : 0.0);
  }

  function setSize() {
    const rect = container.getBoundingClientRect();
    const width = Math.max(1, Math.floor(rect.width * config.dpr));
    const height = Math.max(1, Math.floor(rect.height * config.dpr));
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
      gl.viewport(0, 0, width, height);
      gl.useProgram(program);
      gl.uniform2f(uniforms.uResolution, width, height);
    }
  }

  function render() {
    gl.useProgram(program);
    gl.bindVertexArray(vao);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  const canAnimate = () => isVisible && isPageVisible && !isPaused && !reducedMotion.matches;

  function loop(now) {
    frameId = 0;
    if (!canAnimate()) return;

    const delta = Math.min((now - previousTime) / 1000, 0.1);
    previousTime = now;
    elapsed += delta;

    if (now - lastRenderTime >= 1000 / config.fps - 0.5) {
      gl.useProgram(program);
      gl.uniform1f(uniforms.uTime, elapsed);
      render();
      lastRenderTime = now;
    }

    frameId = requestAnimationFrame(loop);
  }

  function start() {
    if (!canAnimate() || frameId !== 0) return;
    previousTime = performance.now();
    frameId = requestAnimationFrame(loop);
  }

  function stop() {
    if (frameId !== 0) cancelAnimationFrame(frameId);
    frameId = 0;
  }

  const resizeObserver = new ResizeObserver(() => {
    setSize();
    render();
  });
  resizeObserver.observe(container);

  const intersectionObserver = new IntersectionObserver(([entry]) => {
    isVisible = entry.isIntersecting;
    if (canAnimate()) start();
    else stop();
  }, { threshold: 0 });
  intersectionObserver.observe(container);

  const handleVisibility = () => {
    isPageVisible = !document.hidden;
    if (canAnimate()) start();
    else stop();
  };
  document.addEventListener('visibilitychange', handleVisibility);

  updateUniforms();
  setSize();
  render();
  start();

  return {
    destroy() {
      stop();
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      document.removeEventListener('visibilitychange', handleVisibility);
      if (canvas.parentNode === container) container.removeChild(canvas);
      gl.getExtension('WEBGL_lose_context')?.loseContext();
    },
    update(newOptions) {
      Object.assign(config, newOptions);
      updateUniforms();
      render();
    }
  };
}

window.GhostFibers = { init: initGhostFibers };
