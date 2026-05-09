// frontend/app/components/twin/Robot3D.tsx
// Three.js — simplified Go2 3D viewer
// Joints color-coded by health: green/amber/red
// No URDF loader needed — geometric representation

"use client";
import { useEffect, useRef } from "react";
import * as THREE from "three";

interface JointHealth {
  health: number;
  temp: number;
  status: "ok" | "warning" | "critical";
}

interface Robot3DProps {
  joints: Record<string, JointHealth>;
}

// Joint 3D positions on Go2 body (relative to center)
const JOINT_POSITIONS: Record<string, [number, number, number]> = {
  FR_hip:   [ 0.2,  0,  0.15], FR_thigh: [ 0.2, -0.1,  0.15], FR_calf: [ 0.2, -0.25,  0.15],
  FL_hip:   [ 0.2,  0, -0.15], FL_thigh: [ 0.2, -0.1, -0.15], FL_calf: [ 0.2, -0.25, -0.15],
  RR_hip:   [-0.2,  0,  0.15], RR_thigh: [-0.2, -0.1,  0.15], RR_calf: [-0.2, -0.25,  0.15],
  RL_hip:   [-0.2,  0, -0.15], RL_thigh: [-0.2, -0.1, -0.15], RL_calf: [-0.2, -0.25, -0.15],
};

function healthToColor(health: number): THREE.Color {
  if (health > 70) return new THREE.Color(0x22c55e);  // green
  if (health > 40) return new THREE.Color(0xf59e0b);  // amber
  return new THREE.Color(0xef4444);                    // red
}

export default function Robot3D({ joints }: Robot3DProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<{
    renderer: THREE.WebGLRenderer;
    scene: THREE.Scene;
    jointMeshes: Record<string, THREE.Mesh>;
    animId: number;
  } | null>(null);

  useEffect(() => {
    if (!mountRef.current) return;
    const W = mountRef.current.clientWidth;
    const H = mountRef.current.clientHeight;

    // ── Scene setup ──
    const scene    = new THREE.Scene();
    scene.background = new THREE.Color(0x0f172a);

    const camera = new THREE.PerspectiveCamera(45, W / H, 0.01, 100);
    camera.position.set(0.8, 0.6, 0.8);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(W, H);
    renderer.shadowMap.enabled = true;
    mountRef.current.appendChild(renderer.domElement);

    // ── Lighting ──
    scene.add(new THREE.AmbientLight(0xffffff, 0.4));
    const dir = new THREE.DirectionalLight(0xffffff, 0.8);
    dir.position.set(1, 2, 1);
    scene.add(dir);

    // ── Robot body ──
    const bodyGeo  = new THREE.BoxGeometry(0.45, 0.1, 0.28);
    const bodyMat  = new THREE.MeshLambertMaterial({ color: 0x1e293b });
    const body     = new THREE.Mesh(bodyGeo, bodyMat);
    body.position.y = 0.05;
    scene.add(body);

    // ── Head ──
    const headGeo = new THREE.BoxGeometry(0.12, 0.08, 0.12);
    const head    = new THREE.Mesh(headGeo, new THREE.MeshLambertMaterial({ color: 0x334155 }));
    head.position.set(0.27, 0.1, 0);
    scene.add(head);

    // ── Grid floor ──
    scene.add(new THREE.GridHelper(2, 20, 0x1e293b, 0x1e293b));

    // ── Joint spheres ──
    const jointMeshes: Record<string, THREE.Mesh> = {};
    Object.entries(JOINT_POSITIONS).forEach(([name, pos]) => {
      const geo  = new THREE.SphereGeometry(0.025, 12, 12);
      const mat  = new THREE.MeshLambertMaterial({ color: 0x22c55e });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.set(...pos);
      scene.add(mesh);
      jointMeshes[name] = mesh;
    });

    // ── Leg bones (lines between joints) ──
    const legPairs = [
      ["FR_hip","FR_thigh"], ["FR_thigh","FR_calf"],
      ["FL_hip","FL_thigh"], ["FL_thigh","FL_calf"],
      ["RR_hip","RR_thigh"], ["RR_thigh","RR_calf"],
      ["RL_hip","RL_thigh"], ["RL_thigh","RL_calf"],
    ];
    legPairs.forEach(([a, b]) => {
      const pa = JOINT_POSITIONS[a], pb = JOINT_POSITIONS[b];
      const points = [new THREE.Vector3(...pa), new THREE.Vector3(...pb)];
      const geo  = new THREE.BufferGeometry().setFromPoints(points);
      const mat  = new THREE.LineBasicMaterial({ color: 0x475569 });
      scene.add(new THREE.Line(geo, mat));
    });

    // ── Slow rotation ──
    let angle = 0;
    let animId = 0;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      angle += 0.005;
      camera.position.x = Math.sin(angle) * 1.0;
      camera.position.z = Math.cos(angle) * 1.0;
      camera.lookAt(0, 0, 0);
      renderer.render(scene, camera);
    };
    animate();

    sceneRef.current = { renderer, scene, jointMeshes, animId };

    return () => {
      cancelAnimationFrame(animId);
      renderer.dispose();
      mountRef.current?.removeChild(renderer.domElement);
    };
  }, []);

  // ── Update joint colors on health change ──
  useEffect(() => {
    if (!sceneRef.current) return;
    const { jointMeshes } = sceneRef.current;
    Object.entries(joints).forEach(([name, data]) => {
      const mesh = jointMeshes[name];
      if (mesh) {
        (mesh.material as THREE.MeshLambertMaterial).color = healthToColor(data.health);
      }
    });
  }, [joints]);

  return (
    <div ref={mountRef} className="w-full h-full rounded-lg overflow-hidden" />
  );
}
