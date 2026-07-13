import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface BookCallModalProps {
  isOpen: boolean;
  onClose: () => void;
  phoneNumber: string;
  theme: {
    text: string;
    background: string;
    card: string;
    cardBorder: string;
    accent: string;
    inputBg: string;
  };
}

export function BookCallModal({
  isOpen,
  onClose,
  phoneNumber,
  theme,
}: BookCallModalProps) {
  const [step, setStep] = useState<"form" | "confirmation">("form");
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    phone: "",
    topic: "",
  });
  const [loading, setLoading] = useState(false);

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.name || !formData.email) {
      alert("Please fill in all required fields");
      return;
    }

    setLoading(true);
    try {
      // Log booking request to backend
      await fetch("http://localhost:8000/api/voice/call-summary", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          call_id: `pending_${Date.now()}`,
          caller_name: formData.name,
          caller_email: formData.email,
          caller_phone: formData.phone,
          topic: formData.topic,
          booking_confirmed: false,
        }),
      }).catch(() => {
        // Silently fail if backend not available
      });

      setStep("confirmation");
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (step === "confirmation") {
      setStep("form");
      setFormData({ name: "", email: "", phone: "", topic: "" });
      onClose();
    } else {
      onClose();
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={handleClose}
            className="fixed inset-0 bg-black/50 z-40"
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="fixed inset-0 flex items-center justify-center z-50 p-4"
          >
            <div
              className="rounded-2xl p-6 max-w-md w-full shadow-xl border"
              style={{
                background: theme.card,
                borderColor: theme.cardBorder,
              }}
            >
              {step === "form" ? (
                <>
                  <h2
                    className="text-2xl font-bold mb-2"
                    style={{ color: theme.text }}
                  >
                    📞 Schedule a Call
                  </h2>
                  <p className="mb-4" style={{ color: theme.text }}>
                    Chat with Shubham directly about opportunities & questions
                  </p>

                  <form onSubmit={handleSubmit} className="space-y-4">
                    {/* Name */}
                    <div>
                      <label
                        className="block text-sm font-medium mb-1"
                        style={{ color: theme.text }}
                      >
                        Your Name *
                      </label>
                      <input
                        type="text"
                        name="name"
                        value={formData.name}
                        onChange={handleInputChange}
                        placeholder="John Doe"
                        className="w-full px-3 py-2 rounded-lg border focus:outline-none focus:ring-2"
                        style={{
                          background: theme.inputBg,
                          borderColor: theme.cardBorder,
                          color: theme.text,
                          focusRingColor: theme.accent,
                        }}
                      />
                    </div>

                    {/* Email */}
                    <div>
                      <label
                        className="block text-sm font-medium mb-1"
                        style={{ color: theme.text }}
                      >
                        Email *
                      </label>
                      <input
                        type="email"
                        name="email"
                        value={formData.email}
                        onChange={handleInputChange}
                        placeholder="john@example.com"
                        className="w-full px-3 py-2 rounded-lg border focus:outline-none focus:ring-2"
                        style={{
                          background: theme.inputBg,
                          borderColor: theme.cardBorder,
                          color: theme.text,
                        }}
                      />
                    </div>

                    {/* Phone */}
                    <div>
                      <label
                        className="block text-sm font-medium mb-1"
                        style={{ color: theme.text }}
                      >
                        Your Phone (Optional)
                      </label>
                      <input
                        type="tel"
                        name="phone"
                        value={formData.phone}
                        onChange={handleInputChange}
                        placeholder="+1 (555) 123-4567"
                        className="w-full px-3 py-2 rounded-lg border focus:outline-none focus:ring-2"
                        style={{
                          background: theme.inputBg,
                          borderColor: theme.cardBorder,
                          color: theme.text,
                        }}
                      />
                    </div>

                    {/* Topic */}
                    <div>
                      <label
                        className="block text-sm font-medium mb-1"
                        style={{ color: theme.text }}
                      >
                        What's this about?
                      </label>
                      <textarea
                        name="topic"
                        value={formData.topic}
                        onChange={handleInputChange}
                        placeholder="Job opportunity, project discussion, etc."
                        rows={3}
                        className="w-full px-3 py-2 rounded-lg border focus:outline-none focus:ring-2 resize-none"
                        style={{
                          background: theme.inputBg,
                          borderColor: theme.cardBorder,
                          color: theme.text,
                        }}
                      />
                    </div>

                    {/* Buttons */}
                    <div className="flex gap-3 mt-6">
                      <button
                        type="button"
                        onClick={handleClose}
                        className="flex-1 px-4 py-2 rounded-lg border transition-colors"
                        style={{
                          borderColor: theme.cardBorder,
                          color: theme.text,
                        }}
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={loading}
                        className="flex-1 px-4 py-2 rounded-lg font-medium text-white transition-all disabled:opacity-50"
                        style={{
                          background: theme.accent,
                        }}
                      >
                        {loading ? "Preparing..." : "Get Phone Number"}
                      </button>
                    </div>
                  </form>
                </>
              ) : (
                <>
                  {/* Confirmation Step */}
                  <div className="text-center">
                    <motion.div
                      animate={{ scale: [1, 1.1, 1] }}
                      transition={{ duration: 0.5 }}
                      className="text-5xl mb-4"
                    >
                      ✅
                    </motion.div>

                    <h2
                      className="text-2xl font-bold mb-2"
                      style={{ color: theme.text }}
                    >
                      Ready to Call!
                    </h2>

                    <p className="mb-4" style={{ color: theme.text }}>
                      Here's your phone number to call Shubham directly:
                    </p>

                    {/* Phone Number Display */}
                    <motion.div
                      initial={{ scale: 0.95 }}
                      animate={{ scale: 1 }}
                      className="my-6 p-4 rounded-lg border-2"
                      style={{
                        background: theme.inputBg,
                        borderColor: theme.accent,
                      }}
                    >
                      <p
                        className="text-sm opacity-70 mb-1"
                        style={{ color: theme.text }}
                      >
                        Call this number:
                      </p>
                      <p
                        className="text-3xl font-bold tracking-wider"
                        style={{ color: theme.accent }}
                      >
                        {phoneNumber}
                      </p>
                    </motion.div>

                    <p
                      className="text-sm mb-6 opacity-75"
                      style={{ color: theme.text }}
                    >
                      Your info has been recorded. When you call, Shubham's AI
                      will greet you and can book meetings directly on his
                      calendar.
                    </p>

                    <button
                      onClick={handleClose}
                      className="w-full px-4 py-2 rounded-lg font-medium text-white transition-all"
                      style={{
                        background: theme.accent,
                      }}
                    >
                      Done
                    </button>
                  </div>
                </>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
