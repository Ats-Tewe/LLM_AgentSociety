import os
import json
import random
import argparse

def main():
    parser = argparse.ArgumentParser(description="Sample dummy dataset and generate tasks and groundtruth")
    parser.add_argument("--input", type=str, default="dummy_dataset/review.json", help="Path to input review.json")
    parser.add_argument("--ratio", type=float, default=0.01, help="Proportion of data to sample")
    parser.add_argument("--task_dir", type=str, default="dummy_tasks", help="Output directory for tasks")
    parser.add_argument("--gt_dir", type=str, default="dummy_groundtruth", help="Output directory for groundtruth")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    
    args = parser.parse_args()
    
    random.seed(args.seed)
    
    if not os.path.exists(args.input):
        print(f"❌ Input file not found: {args.input}")
        return

    with open(args.input, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    num_samples = max(1, int(len(lines) * args.ratio))
    sampled_lines = random.sample(lines, num_samples)
    
    os.makedirs(args.task_dir, exist_ok=True)
    os.makedirs(args.gt_dir, exist_ok=True)
    
    for i, line in enumerate(sampled_lines, 1):
        data = json.loads(line)
        
        task_file = os.path.join(args.task_dir, f"task_{i}.json")
        gt_file = os.path.join(args.gt_dir, f"groundtruth_{i}.json")
        
        if "text" in data and "review" not in data:
            data["review"] = data["text"]
            
        # Groundtruth gets all data
        with open(gt_file, 'w', encoding='utf-8') as gf:
            json.dump(data, gf, ensure_ascii=False, indent=2)
            
        # Tasks keeps identifiers
        task_data = {
            "type": "user_behavior_simulation",
            "review_id": data.get("review_id"),
            "user_id": data.get("user_id"),
            "item_id": data.get("item_id"),
            "date": data.get("date")
        }
            
        with open(task_file, 'w', encoding='utf-8') as tf:
            json.dump(task_data, tf, ensure_ascii=False, indent=2)
            
    print(f"✅ Sampled {num_samples} reviews from {len(lines)} total (ratio={args.ratio}).")
    print(f"✅ Task files generated in: {args.task_dir} (e.g. task_1.json)")
    print(f"✅ Groundtruth files generated in: {args.gt_dir} (e.g. groundtruth_1.json)")

if __name__ == "__main__":
    main()
