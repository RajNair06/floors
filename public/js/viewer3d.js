/**
 * 3D floor-plan viewer using Three.js (vendored).
 *
 * Coordinate mapping: plan x → Three.js X, plan y → -Z (y grows down in 2D).
 * Three.js Y is up (height).
 */

import * as THREE from "../vendor/three/three.module.min.js";
import { OrbitControls } from "../vendor/three/OrbitControls.js";

// Room colour palette (matches SVG renderer).
const ROOM_COLOURS = {
  living: 0xe8f4f8,
  kitchen: 0xfef3c7,
  dining: 0xfde8e8,
  bedroom: 0xe0e7ff,
  bathroom: 0xd1fae5,
  hallway: 0xf3f4f6,
  study: 0xfef9c3,
  utility: 0xe5e7eb,
  storage: 0xd6d3d1,
};

const WALL_COLOUR = 0xf5f5f0;
const DOOR_COLOUR = 0x2563eb;
const EXTERIOR_DOOR_COLOUR = 0x059669;
const WINDOW_COLOUR = 0x7dd3fc;
const VIOLATION_COLOUR = 0xdc2626;

const WALL_THICKNESS = 0.08; // metres — visual only, not used in validation.
const DOOR_HEIGHT = 2.1;
const WINDOW_BOTTOM = 0.9;
const WINDOW_HEIGHT = 1.2;

/**
 * Check if WebGL is available.
 */
export function isWebGLAvailable() {
  try {
    const canvas = document.createElement("canvas");
    return !!(
      window.WebGLRenderingContext &&
      (canvas.getContext("webgl") || canvas.getContext("experimental-webgl"))
    );
  } catch {
    return false;
  }
}

/**
 * Create and manage a 3D viewer for a floor plan.
 */
export class FloorPlan3D {
  constructor(container) {
    this.container = container;
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.controls = null;
    this.animationId = null;
    this._disposed = false;
  }

  /**
   * Initialize the Three.js scene. Call once.
   */
  init() {
    const w = this.container.clientWidth || 600;
    const h = this.container.clientHeight || 400;

    // Scene.
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0xf0f0f0);

    // Camera.
    this.camera = new THREE.PerspectiveCamera(50, w / h, 0.1, 500);
    this.camera.position.set(10, 12, 14);

    // Renderer.
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.setSize(w, h);
    this.renderer.shadowMap.enabled = true;
    this.container.innerHTML = "";
    this.container.appendChild(this.renderer.domElement);

    // Controls.
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.target.set(0, 0, 0);

    // Lights.
    const ambient = new THREE.AmbientLight(0xffffff, 0.6);
    this.scene.add(ambient);

    const dir = new THREE.DirectionalLight(0xffffff, 0.8);
    dir.position.set(10, 20, 10);
    dir.castShadow = true;
    dir.shadow.mapSize.width = 1024;
    dir.shadow.mapSize.height = 1024;
    this.scene.add(dir);

    // Ground plane.
    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(100, 100),
      new THREE.MeshStandardMaterial({ color: 0xe0e0e0 })
    );
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.02;
    ground.receiveShadow = true;
    this.scene.add(ground);

    // Resize handler.
    this._onResize = () => {
      if (this._disposed) return;
      const nw = this.container.clientWidth || 600;
      const nh = this.container.clientHeight || 400;
      this.camera.aspect = nw / nh;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(nw, nh);
    };
    window.addEventListener("resize", this._onResize);

    // Animation loop.
    this._animate = () => {
      if (this._disposed) return;
      this.animationId = requestAnimationFrame(this._animate);
      this.controls.update();
      this.renderer.render(this.scene, this.camera);
    };
    this._animate();
  }

  /**
   * Load a plan and render it in 3D.
   * @param {object} plan — parsed plan object
   * @param {Array} violations — list of violation objects (optional)
   */
  loadPlan(plan, violations = []) {
    // Clear previous geometry (keep lights and ground).
    this._clearPlan();

    if (!plan.rooms || plan.rooms.length === 0) {
      return;
    }

    const ceilingHeight = plan.ceiling_height || 2.7;

    // Compute bounds to centre the view.
    const xs = plan.rooms.flatMap((r) => [r.x, r.x + r.w]);
    const ys = plan.rooms.flatMap((r) => [r.y, r.y + r.h]);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const cx = (minX + maxX) / 2;
    const cz = (minY + maxY) / 2;

    // Build violation room set.
    const violationRooms = new Set();
    for (const v of violations) {
      if (v.room_ids) {
        for (const rid of v.room_ids) violationRooms.add(rid);
      }
    }

    // Build rooms.
    for (const room of plan.rooms) {
      this._addRoom(room, ceilingHeight, cx, cz, violationRooms.has(room.id));
    }

    // Build doors.
    const roomMap = {};
    for (const r of plan.rooms) roomMap[r.id] = r;
    for (const door of plan.doors) {
      const fromRoom = roomMap[door.from];
      if (!fromRoom) continue;
      this._addDoor(door, fromRoom, ceilingHeight, cx, cz);
    }

    // Build windows.
    for (const win of plan.windows) {
      const room = roomMap[win.room];
      if (!room) continue;
      this._addWindow(win, room, ceilingHeight, cx, cz);
    }

    // Centre camera.
    this.controls.target.set(0, ceilingHeight / 2, 0);
    const span = Math.max(maxX - minX, maxY - minY);
    const dist = span * 1.2;
    this.camera.position.set(dist * 0.8, dist * 0.9, dist * 0.8);
    this.controls.update();
  }

  /**
   * Reset camera to top-down view.
   */
  resetTopDown() {
    if (!this.controls) return;
    this.camera.position.set(0, 25, 0.01);
    this.controls.target.set(0, 0, 0);
    this.controls.update();
  }

  /**
   * Reset camera to perspective view.
   */
  resetPerspective() {
    if (!this.controls) return;
    this.camera.position.set(10, 12, 14);
    this.controls.target.set(0, 1, 0);
    this.controls.update();
  }

  /**
   * Clean up Three.js resources.
   */
  dispose() {
    this._disposed = true;
    if (this.animationId) cancelAnimationFrame(this.animationId);
    window.removeEventListener("resize", this._onResize);
    if (this.controls) this.controls.dispose();
    if (this.renderer) {
      this.renderer.dispose();
      this.renderer.domElement.remove();
    }
    this._clearPlan();
  }

  // -----------------------------------------------------------------------
  // Internal helpers
  // -----------------------------------------------------------------------

  _clearPlan() {
    if (!this.scene) return;
    const toRemove = [];
    this.scene.traverse((obj) => {
      if (obj.userData.isPlanElement) toRemove.push(obj);
    });
    for (const obj of toRemove) {
      this.scene.remove(obj);
      if (obj.geometry) obj.geometry.dispose();
      if (obj.material) {
        if (Array.isArray(obj.material)) {
          obj.material.forEach((m) => m.dispose());
        } else {
          obj.material.dispose();
        }
      }
    }
  }

  /**
   * Map plan coordinates to Three.js world coordinates.
   * Plan x → Three.js X, plan y → -Z, plan y=0 is at z=0.
   */
  _mapX(x, cx) {
    return x - cx;
  }
  _mapZ(y, cz) {
    return -(y - cz);
  }

  _addRoom(room, ceilingHeight, cx, cz, isViolation) {
    const px = this._mapX(room.x + room.w / 2, cx);
    const pz = this._mapZ(room.y + room.h / 2, cz);
    const colour = ROOM_COLOURS[room.type] || 0xf5f5f5;

    // Floor.
    const floorGeo = new THREE.BoxGeometry(room.w, 0.05, room.h);
    const floorMat = new THREE.MeshStandardMaterial({
      color: colour,
      roughness: 0.8,
    });
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.position.set(px, 0.025, pz);
    floor.receiveShadow = true;
    floor.userData.isPlanElement = true;
    floor.userData.roomId = room.id;
    this.scene.add(floor);

    // Walls (4 sides).
    const wallMat = new THREE.MeshStandardMaterial({
      color: WALL_COLOUR,
      roughness: 0.6,
      side: THREE.DoubleSide,
    });

    const walls = [
      // N wall (top edge in 2D, so z = -(room.y - cz) + room.h/2, i.e. the negative-z side)
      {
        w: room.w,
        h: ceilingHeight,
        d: WALL_THICKNESS,
        x: px,
        y: ceilingHeight / 2,
        z: pz + room.h / 2,
      },
      // S wall (bottom edge)
      {
        w: room.w,
        h: ceilingHeight,
        d: WALL_THICKNESS,
        x: px,
        y: ceilingHeight / 2,
        z: pz - room.h / 2,
      },
      // W wall (left edge)
      {
        w: WALL_THICKNESS,
        h: ceilingHeight,
        d: room.h,
        x: px - room.w / 2,
        y: ceilingHeight / 2,
        z: pz,
      },
      // E wall (right edge)
      {
        w: WALL_THICKNESS,
        h: ceilingHeight,
        d: room.h,
        x: px + room.w / 2,
        y: ceilingHeight / 2,
        z: pz,
      },
    ];

    for (const w of walls) {
      const geo = new THREE.BoxGeometry(w.w, w.h, w.d);
      const mesh = new THREE.Mesh(geo, wallMat.clone());
      mesh.position.set(w.x, w.y, w.z);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      mesh.userData.isPlanElement = true;
      mesh.userData.roomId = room.id;
      this.scene.add(mesh);
    }

    // Violation outline (red wireframe box).
    if (isViolation) {
      const outlineGeo = new THREE.BoxGeometry(room.w, ceilingHeight, room.h);
      const edges = new THREE.EdgesGeometry(outlineGeo);
      const line = new THREE.LineSegments(
        edges,
        new THREE.LineBasicMaterial({ color: VIOLATION_COLOUR, linewidth: 2 })
      );
      line.position.set(px, ceilingHeight / 2, pz);
      line.userData.isPlanElement = true;
      this.scene.add(line);
    }

    // Room label (floating text sprite).
    const label = this._makeTextSprite(room.name, 0.5);
    label.position.set(px, ceilingHeight + 0.3, pz);
    label.userData.isPlanElement = true;
    this.scene.add(label);
  }

  _addDoor(door, fromRoom, ceilingHeight, cx, cz) {
    // px, pz are the top-left corner of the room in 3D coordinates.
    // px = mapX(fromRoom.x) = left edge, pz = mapZ(fromRoom.y) = top edge (large z).
    const px = this._mapX(fromRoom.x, cx);
    const pz = this._mapZ(fromRoom.y, cz);
    const isExterior = door.to === "outside";
    const colour = isExterior ? EXTERIOR_DOOR_COLOUR : DOOR_COLOUR;

    const doorH = Math.min(DOOR_HEIGHT, ceilingHeight);
    let dx, dz, dw, dd;

    // offset is distance from wall start (left end for N/S, top end for E/W).
    // Top end (small y) maps to large z; bottom end (large y) maps to small z.
    switch (door.wall) {
      case "N":
        // N wall = top edge in 2D (y = fromRoom.y) → z = pz.
        dx = px + door.offset + door.width / 2;
        dz = pz;
        dw = door.width;
        dd = WALL_THICKNESS + 0.02;
        break;
      case "S":
        // S wall = bottom edge in 2D (y = fromRoom.y + fromRoom.h) → z = pz - fromRoom.h.
        dx = px + door.offset + door.width / 2;
        dz = pz - fromRoom.h;
        dw = door.width;
        dd = WALL_THICKNESS + 0.02;
        break;
      case "W":
        // W wall = left edge in 2D (x = fromRoom.x) → x = px.
        // offset runs from top (pz) to bottom (pz - fromRoom.h).
        dx = px;
        dz = pz - door.offset - door.width / 2;
        dw = WALL_THICKNESS + 0.02;
        dd = door.width;
        break;
      case "E":
        // E wall = right edge in 2D (x = fromRoom.x + fromRoom.w) → x = px + fromRoom.w.
        // offset runs from top (pz) to bottom (pz - fromRoom.h).
        dx = px + fromRoom.w;
        dz = pz - door.offset - door.width / 2;
        dw = WALL_THICKNESS + 0.02;
        dd = door.width;
        break;
    }

    const geo = new THREE.BoxGeometry(dw, doorH, dd);
    const mat = new THREE.MeshStandardMaterial({
      color: colour,
      roughness: 0.4,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(dx, doorH / 2, dz);
    mesh.userData.isPlanElement = true;
    this.scene.add(mesh);
  }

  _addWindow(win, room, ceilingHeight, cx, cz) {
    // px, pz are the top-left corner of the room in 3D coordinates.
    const px = this._mapX(room.x, cx);
    const pz = this._mapZ(room.y, cz);

    const winBottom = Math.min(WINDOW_BOTTOM, ceilingHeight - WINDOW_HEIGHT);
    const winH = Math.min(WINDOW_HEIGHT, ceilingHeight - winBottom);

    let wx, wz, ww, wd;

    switch (win.wall) {
      case "N":
        // N wall = top edge (y = room.y) → z = pz.
        wx = px + win.offset + win.width / 2;
        wz = pz;
        ww = win.width;
        wd = WALL_THICKNESS + 0.03;
        break;
      case "S":
        // S wall = bottom edge (y = room.y + room.h) → z = pz - room.h.
        wx = px + win.offset + win.width / 2;
        wz = pz - room.h;
        ww = win.width;
        wd = WALL_THICKNESS + 0.03;
        break;
      case "W":
        // W wall = left edge (x = room.x) → x = px.
        wx = px;
        wz = pz - win.offset - win.width / 2;
        ww = WALL_THICKNESS + 0.03;
        wd = win.width;
        break;
      case "E":
        // E wall = right edge (x = room.x + room.w) → x = px + room.w.
        wx = px + room.w;
        wz = pz - win.offset - win.width / 2;
        ww = WALL_THICKNESS + 0.03;
        wd = win.width;
        break;
    }

    const geo = new THREE.BoxGeometry(ww, winH, wd);
    const mat = new THREE.MeshStandardMaterial({
      color: WINDOW_COLOUR,
      roughness: 0.1,
      transparent: true,
      opacity: 0.6,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(wx, winBottom + winH / 2, wz);
    mesh.userData.isPlanElement = true;
    this.scene.add(mesh);
  }

  /**
   * Create a text sprite for room labels.
   */
  _makeTextSprite(text, scale = 1) {
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    canvas.width = 256;
    canvas.height = 64;

    ctx.fillStyle = "rgba(255,255,255,0.85)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "#374151";
    ctx.lineWidth = 2;
    ctx.strokeRect(1, 1, canvas.width - 2, canvas.height - 2);

    ctx.fillStyle = "#1f2937";
    ctx.font = "bold 28px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, canvas.width / 2, canvas.height / 2);

    const texture = new THREE.CanvasTexture(canvas);
    texture.needsUpdate = true;

    const spriteMat = new THREE.SpriteMaterial({ map: texture, depthTest: false });
    const sprite = new THREE.Sprite(spriteMat);
    sprite.scale.set(scale * 4, scale, 1);
    return sprite;
  }
}
